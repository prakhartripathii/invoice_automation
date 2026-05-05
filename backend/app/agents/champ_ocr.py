"""Agent 2 — Champ OCR.

Two backends, picked at runtime:
  1. **Local LayoutLMv3** (champ-v2-resumed) for digital PDFs — preferred.
     We subprocess into the `ocr_engine` venv so we don't need torch/transformers
     in the backend venv. Driven by env vars OCR_ENGINE_PYTHON, OCR_MODEL_PATH.
  2. **OCR.space** as fallback for images / non-PDF inputs / when the local
     model is misconfigured or fails.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from random import Random
from typing import Any, Dict, List, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from app.agents.base import BaseAgent
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.invoice import InvoiceExtracted, InvoiceItemCreate
from app.utils.circuit_breaker import get_breaker
from app.utils.exceptions import OCRFailureError

log = get_logger(__name__)
_breaker = get_breaker("ocr_space", fail_max=5, reset_timeout=60)


# ---- Local LayoutLMv3 helpers ----
def _local_model_configured() -> bool:
    py = settings.ocr_engine_python
    model = settings.ocr_model_path
    return bool(py and model and Path(py).exists() and Path(model).exists())


def _try_sidecar(file_bytes: bytes, timeout: float = 60.0) -> Optional[Dict[str, Any]]:
    """POST PDF to the persistent sidecar. Returns fields dict or None if
    sidecar isn't reachable (caller should fall back to subprocess).

    Any HTTP-level error from the sidecar is treated as fatal (raises
    OCRFailureError) — only a connection refusal returns None.
    """
    base = (settings.ocr_sidecar_url or "").rstrip("/")
    if not base:
        return None
    try:
        r = requests.post(
            f"{base}/extract",
            data=file_bytes,
            headers={"Content-Type": "application/pdf"},
            timeout=timeout,
        )
    except requests.exceptions.ConnectionError:
        return None  # sidecar not running — fall back
    if r.status_code != 200:
        raise OCRFailureError(f"Sidecar returned {r.status_code}: {r.text[:300]}")
    try:
        return r.json()
    except ValueError as e:
        raise OCRFailureError(f"Sidecar returned non-JSON: {e}") from e


def _run_local_layoutlm(file_bytes: bytes, suffix: str = ".pdf") -> Dict[str, Any]:
    """Subprocess into ocr_engine venv, return the parsed field dict.

    Raises OCRFailureError on any failure so the caller can fall back.
    """
    py = settings.ocr_engine_python
    model = settings.ocr_model_path
    project_root = Path(__file__).resolve().parents[3]  # .../Invoice-Automation-Backend

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)
    try:
        proc = subprocess.run(
            [
                py, "-m", "ocr_engine.scripts.extract_pdf",
                "--pdf", str(tmp_path),
                "--model", model,
                "--json-only", "--mean-conf",
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    if proc.returncode != 0:
        raise OCRFailureError(
            f"Local model subprocess failed (rc={proc.returncode}): {proc.stderr[-400:]}"
        )

    # Take the LAST non-empty stdout line — tqdm/log noise may precede.
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if not lines:
        raise OCRFailureError(f"Local model produced no output. stderr={proc.stderr[-400:]}")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as e:
        raise OCRFailureError(f"Local model output not JSON: {e}; tail={lines[-1][:200]}") from e


# ---- Field parsing helpers ----
_DATE_FORMATS = ("%d-%b-%y", "%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y")


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    s = s.strip().rstrip(",")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(s: Optional[str]) -> Optional[Decimal]:
    if not s:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", s.replace(",", ""))
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _map_local_fields_to_schema(fields: Dict[str, Any]) -> InvoiceExtracted:
    """Convert the LayoutLMv3 field dict (string values) to InvoiceExtracted."""
    total = _parse_amount(fields.get("total_amount"))
    cgst = _parse_amount(fields.get("cgst")) or Decimal("0")
    sgst = _parse_amount(fields.get("gst")) or Decimal("0")
    igst = _parse_amount(fields.get("igst")) or Decimal("0")
    tax = cgst + sgst + igst
    subtotal = (total - tax) if (total is not None and tax) else total

    mean_conf = float(fields.get("__mean_confidence", 0.85))
    confidence_scores = {
        k: mean_conf for k in (
            "vendor_name", "invoice_number", "invoice_date",
            "total_amount", "vendor_email", "vendor_phone",
        ) if fields.get(k)
    }

    return InvoiceExtracted(
        vendor_name=fields.get("vendor_name"),
        invoice_number=fields.get("invoice_number"),
        invoice_date=_parse_date(fields.get("invoice_date")) or date.today(),
        due_date=_parse_date(fields.get("due_date")) or date.today(),
        currency="INR" if any(fields.get(k) for k in ("cgst", "gst", "igst")) else "USD",
        subtotal=subtotal,
        tax_amount=tax if tax else Decimal("0.00"),
        total_amount=total if total is not None else Decimal("0.00"),
        purchase_order=fields.get("purchase_order"),
        items=[],
        confidence_scores=confidence_scores,
        raw={"engine": "layoutlmv3_local", "fields": fields},
    )

@dataclass
class ChampOCRInput:
    file_bytes: bytes
    mime_type: str
    file_hash: str

class ChampOCRAgent(BaseAgent[ChampOCRInput, InvoiceExtracted]):
    name = "champ_ocr_space"

    def _run(self, inputs: ChampOCRInput) -> InvoiceExtracted:
        is_pdf = "pdf" in (inputs.mime_type or "").lower()

        # 1) Sidecar (persistent process, model already in memory) — fastest path.
        if is_pdf:
            try:
                fields = _try_sidecar(inputs.file_bytes)
                if fields is not None:
                    log.info("local_layoutlm_sidecar_ok",
                             fields=list(fields.keys()),
                             conf=fields.get("__mean_confidence"))
                    return _map_local_fields_to_schema(fields)
                log.info("sidecar_unreachable_falling_back_to_subprocess")
            except OCRFailureError as e:
                log.warning("sidecar_failed_falling_back_to_subprocess", error=str(e))

        # 2) Subprocess into ocr_engine venv (fallback when sidecar isn't running)
        if is_pdf and _local_model_configured():
            try:
                fields = _run_local_layoutlm(inputs.file_bytes, suffix=".pdf")
                log.info("local_layoutlm_subprocess_ok",
                         fields=list(fields.keys()),
                         conf=fields.get("__mean_confidence"))
                return _map_local_fields_to_schema(fields)
            except OCRFailureError as e:
                log.warning("local_layoutlm_failed_falling_back_to_ocr_space", error=str(e))

        # 3) Final fallback: OCR.space (images / local model unavailable)
        return self._real_extract(inputs)

    @_breaker
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _real_extract(self, inputs: ChampOCRInput) -> InvoiceExtracted:
        try:
            print(f"\n--- ATTEMPTING REAL OCR: {inputs.file_hash[:8]} ---")
            
            # Using your verified API Key
            # Use mime_type to set correct filename + filetype, otherwise OCR.space 400s.
            mt = (inputs.mime_type or "").lower()
            if "pdf" in mt:
                fname, filetype = "invoice.pdf", "PDF"
            elif "jpeg" in mt or "jpg" in mt:
                fname, filetype = "invoice.jpg", "JPG"
            elif "tiff" in mt or "tif" in mt:
                fname, filetype = "invoice.tif", "TIF"
            else:
                fname, filetype = "invoice.png", "PNG"

            payload = {
                'apikey': settings.ocr_space_api_key or 'K89120996988957',
                'language': 'eng',
                'isTable': True,
                'OCREngine': '2',
                'filetype': filetype,
            }

            files = {'file': (fname, inputs.file_bytes, inputs.mime_type)}
            
            response = requests.post(
                "https://api.ocr.space/parse/image",
                files=files,
                data=payload,
                timeout=30
            )
            
            if response.status_code == 403:
                print("!!! 403 FORBIDDEN: Check your API Key usage limit !!!")
                
            response.raise_for_status()
            result = response.json()

            if result.get('OCRExitCode') != 1:
                error_msg = result.get('ErrorMessage', 'Unknown error')
                raise OCRFailureError(f"OCR.space Error: {error_msg}")

            parsed_text = result['ParsedResults'][0]['ParsedText']
            
            # Print for terminal debugging
            print("\n" + "="*50)
            print("REAL TEXT SCANNED:")
            print(parsed_text)
            print("="*50 + "\n")
            
            return _map_raw_text_to_schema(parsed_text)

        except Exception as exc:
            log.error("ocr_service_failure", error=str(exc))
            raise OCRFailureError(f"OCR Engine failure: {exc}") from exc

# ------- SMART REAL DATA MAPPER -------
def _map_raw_text_to_schema(text: str) -> InvoiceExtracted:
    """
    Analyzes raw text to find Vendor, Invoice Number, and the Grand Total.
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # 1. Vendor Logic: Pick the first line, but skip headers like "INVOICE"
    vendor = "Unknown Vendor"
    if lines:
        if lines[0].upper() in ["INVOICE", "ESTIMATE", "ESTIMATE NO."] and len(lines) > 1:
            vendor = lines[1]
        else:
            vendor = lines[0]
    
    # 2. Smart Total Logic: Find the highest monetary value
    # Regex looks for $1,900.00, 6300.00, or numbers following currency symbols
    amount_strings = re.findall(r"(?:\$|€|£|₹|·|7)?\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+)", text)
    
    clean_amounts = []
    for s in amount_strings:
        try:
            # Clean string for Decimal conversion (remove commas)
            val = Decimal(s.replace(',', ''))
            # Filter out small numbers that might be quantities (like '1' or '2')
            if val > 10.0: 
                clean_amounts.append(val)
        except:
            continue

    # Assign the maximum value found as the Grand Total
    real_total = max(clean_amounts) if clean_amounts else Decimal("0.00")

    # 3. Invoice Number Logic
    inv_match = re.search(r"(?:INV|Invoice|No|Estimate No\.?)\s*[:.]?\s*([A-Z0-9-]+)", text, re.IGNORECASE)
    inv_no = inv_match.group(1) if inv_match else "EXTRACTED-REAL"

    return InvoiceExtracted(
        vendor_name=vendor,
        invoice_number=inv_no,
        invoice_date=date.today(),
        due_date=date.today(),
        currency="USD",
        subtotal=real_total,
        tax_amount=Decimal("0.00"),
        total_amount=real_total,
        items=[],
        confidence_scores={
            "vendor_name": 1.0, 
            "invoice_number": 1.0,
            "total_amount": 1.0
        },
        raw={"engine": "ocr_space", "full_text": text},
    )

# ------- Mock Helper (Required by challenger_ocr.py) -------
def _mock_extract(seed_hash: str, engine: str) -> InvoiceExtracted:
    r = Random(int(seed_hash[:16], 16))
    return InvoiceExtracted(
        vendor_name=f"MOCK_{engine.upper()}",
        invoice_number=f"INV-{r.randint(1000, 9999)}",
        invoice_date=date.today(),
        total_amount=Decimal("0.00"),
        items=[],
        confidence_scores={},
        raw={"engine": engine, "mocked": True},
    )