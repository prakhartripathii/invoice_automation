"""End-to-end smoke test: PDF -> PyMuPDF text+bbox -> LayoutLMv3 -> field dict.

Bypasses PaddleOCR entirely (we tested earlier that oneDNN crashes on this
Windows install for digital PDFs anyway, and PyMuPDF gives us perfect words
+ boxes for any digitally-generated invoice). For scanned PDFs you'd swap
the OCR backend back in.

Usage:
    python -m ocr_engine.scripts.extract_pdf \
        --pdf "ocr_engine/datasets/custom_invoices_raw/Invoice No.215.pdf" \
        --model D:/invoice_artifacts/champ-v2-resumed
"""
from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import click
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _render_and_extract(pdf_path: Path, page_idx: int, dpi: int = 300):
    """Return (PIL.Image RGB, list[OCRWord], (W,H))."""
    import fitz
    from PIL import Image
    from ocr_engine.ocr.base import OCRWord

    doc = fitz.open(str(pdf_path))
    page = doc.load_page(page_idx)
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    W, H = img.size

    words: list[OCRWord] = []
    raw = page.get_text("words")  # (x0, y0, x1, y1, word, ...)
    for x0, y0, x1, y1, w, *_ in raw:
        if not w or not w.strip():
            continue
        bbox = (
            max(0, min(W, int(x0 * zoom))),
            max(0, min(H, int(y0 * zoom))),
            max(0, min(W, int(x1 * zoom))),
            max(0, min(H, int(y1 * zoom))),
        )
        words.append(OCRWord(text=w.strip(), bbox=bbox, confidence=1.0))
    doc.close()
    return img, words, (W, H)


def _run_model(pil_image, words, image_size, model_path: str):
    """Run LayoutLMv3 on (image, words, boxes) and return Prediction."""
    from ocr_engine.extraction.infer import InvoicePredictor
    from ocr_engine.ocr.base import OCRResult

    # Build a fake OCRResult so we can call _infer_tokens directly.
    ocr_res = OCRResult(words=words, image_size=image_size)
    arr = np.array(pil_image)[:, :, ::-1].copy()  # RGB -> BGR for the predictor's pipeline

    # We can't use InvoicePredictor() because its constructor instantiates PaddleOCR.
    # Instead, instantiate the model+processor directly and reuse _tokens_to_fields.
    import torch
    from transformers import LayoutLMv3ForTokenClassification, LayoutLMv3Processor
    from ocr_engine.config import ID2LABEL
    from ocr_engine.extraction.infer import _tokens_to_fields, enc_word_ids

    processor = LayoutLMv3Processor.from_pretrained(model_path, apply_ocr=False)
    model = LayoutLMv3ForTokenClassification.from_pretrained(model_path)
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    word_texts = [w.text for w in words]
    boxes = ocr_res.normalized_bboxes(1000)

    enc = processor(
        pil_image, word_texts, boxes=boxes,
        truncation=True, padding="max_length", max_length=512, return_tensors="pt",
    )
    enc = {k: v.to(device) for k, v in enc.items()}

    valid = {"input_ids", "attention_mask", "bbox", "pixel_values", "token_type_ids"}
    with torch.no_grad():
        out = model(**{k: v for k, v in enc.items() if k in valid})
    logits = out.logits[0]
    probs = torch.softmax(logits, dim=-1)
    conf, pred = probs.max(dim=-1)
    pred_np = pred.cpu().numpy()
    conf_np = conf.cpu().numpy()

    word_ids = enc_word_ids(processor, word_texts, boxes, pil_image, device)
    word_labels: dict[int, str] = {}
    word_confs: dict[int, list[float]] = {}
    for tok_idx, wid in enumerate(word_ids):
        if wid is None or tok_idx >= len(pred_np):
            continue
        if wid in word_labels:
            word_confs[wid].append(float(conf_np[tok_idx]))
            continue
        word_labels[wid] = ID2LABEL.get(int(pred_np[tok_idx]), "O")
        word_confs[wid] = [float(conf_np[tok_idx])]

    token_labels = [word_labels.get(i, "O") for i in range(len(word_texts))]
    fields = _tokens_to_fields(word_texts, token_labels)
    confs_per_word = [
        sum(word_confs.get(i, [0.0])) / max(1, len(word_confs.get(i, [0.0])))
        for i in range(len(word_texts))
    ]
    mean_conf = float(np.mean(confs_per_word)) if confs_per_word else 0.0
    return fields, token_labels, word_texts, mean_conf


def _merge_fields(per_page: list[dict[str, str]]) -> dict[str, str]:
    """Take the first non-empty value across pages for each field."""
    merged: dict[str, str] = {}
    for d in per_page:
        for k, v in d.items():
            if v and k not in merged:
                merged[k] = v
    return merged


# ---------------------------------------------------------------------------
# Regex-based post-processing fallback. The model handles the spatially-
# anchored fields (vendor name/address, invoice no/date) extremely reliably
# but misses the rare/ambiguous ones (phone, GST values, grand total when
# the page has multiple "Total" cells). For those we fall back to deterministic
# regex rules — same heuristics as the auto-labeler, but applied at inference
# time. This boosts recall without requiring more training data.
# ---------------------------------------------------------------------------
import re as _re

_RE_EMAIL = _re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_RE_PHONE = _re.compile(r"\+\d{10,13}")
_RE_GSTIN = _re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b")
_RE_DATE = _re.compile(r"\b\d{1,2}-[A-Za-z]{3}-\d{2,4}\b")
_RE_AMOUNT = _re.compile(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?")


def _flatten_words(per_page_words: list[list[str]]) -> list[str]:
    return [w for page in per_page_words for w in page]


def _find_amount_after(words: list[str], anchor_pred) -> str | None:
    """Find the first number-like token after the position satisfying anchor_pred."""
    for i, w in enumerate(words):
        if anchor_pred(w) and i + 1 < len(words):
            for j in range(i + 1, min(i + 4, len(words))):
                if _RE_AMOUNT.fullmatch(words[j]):
                    return words[j]
    return None


def _find_grand_total(words: list[str]) -> str | None:
    """The grand total is the token after the last 'Total' before 'Amount Chargeable'.

    Layout pattern: ... 'Total' '<grand_total_amount>' [misc tokens] 'Amount' 'Chargeable' ...
    Some pages also have a smaller 'Total' header earlier (column header), so we
    take the LAST 'Total' that precedes 'Amount Chargeable'.
    """
    # Find 'Amount Chargeable' position (or end of doc as fallback)
    end = len(words)
    for i in range(len(words) - 1):
        if words[i] == "Amount" and words[i + 1] == "Chargeable":
            end = i
            break
    # Walk backwards from `end` to find the last 'Total' followed by an amount
    for i in range(end - 1, 0, -1):
        if words[i] == "Total" and i + 1 < len(words) and _RE_AMOUNT.fullmatch(words[i + 1]):
            return words[i + 1]
    # Fallback: largest amount token in the last 30 tokens before 'Amount Chargeable'
    candidates = [w for w in words[max(0, end - 30):end] if _RE_AMOUNT.fullmatch(w)]
    if not candidates:
        return None
    def to_float(s: str) -> float:
        try:
            return float(s.replace(",", ""))
        except ValueError:
            return 0.0
    return max(candidates, key=to_float)


def postprocess(fields: dict[str, str], all_words: list[str]) -> dict[str, str]:
    out = dict(fields)

    # 1. Email: clean up the "pradeep. manish@..." split case
    if "vendor_email" in out:
        out["vendor_email"] = _re.sub(r"\.\s+", ".", out["vendor_email"]).strip()
    else:
        # Fallback: scan words for an email-like token
        for i, w in enumerate(all_words):
            if _RE_EMAIL.fullmatch(w):
                out["vendor_email"] = w
                break
            # Split case across two tokens
            if w.endswith(".") and i + 1 < len(all_words) and "@" in all_words[i + 1]:
                cand = w + all_words[i + 1]
                if _RE_EMAIL.fullmatch(cand):
                    out["vendor_email"] = cand
                    break

    # 2. Phone: regex over all words
    if "vendor_phone" not in out:
        for w in all_words:
            if _RE_PHONE.fullmatch(w):
                out["vendor_phone"] = w
                break

    # 3. Vendor tax ID (GSTIN): first match if model missed it
    if "vendor_tax_id" not in out:
        for w in all_words:
            if _RE_GSTIN.fullmatch(w):
                out["vendor_tax_id"] = w
                break

    # 4. CGST / SGST(=gst) / IGST values: anchor on the @9%_OUTPUT-style tag
    def _anchor(substr: str):
        return lambda w: substr in w.upper() and "@" in w
    if "cgst" not in out:
        v = _find_amount_after(all_words, _anchor("CGST"))
        if v:
            out["cgst"] = v
    if "gst" not in out:
        v = _find_amount_after(all_words, _anchor("SGST"))
        if v:
            out["gst"] = v
    if "igst" not in out:
        v = _find_amount_after(all_words, _anchor("IGST"))
        if v:
            out["igst"] = v

    # 5. Grand total: trust model only if it's NOT a known tax-amount value;
    # otherwise compute from the "Amount Chargeable" anchor.
    grand = _find_grand_total(all_words)
    if grand:
        # If the model picked a small number that looks like a tax row, override.
        cur = out.get("total_amount")
        if cur is None or (cur in {out.get("cgst"), out.get("gst"), out.get("igst")}):
            out["total_amount"] = grand

    # 6. Invoice date: regex fallback (DD-MMM-YY)
    if "invoice_date" not in out:
        for w in all_words:
            if _RE_DATE.fullmatch(w):
                out["invoice_date"] = w
                break

    # 7. Total quantity: number right before "Service Call Charge"
    if "total_quantity" not in out:
        for i in range(len(all_words) - 3):
            if (all_words[i + 1] == "Service" and all_words[i + 2] == "Call"
                    and all_words[i + 3] == "Charge" and all_words[i].isdigit()):
                out["total_quantity"] = all_words[i]
                break

    return out


@click.command()
@click.option("--pdf", "pdf_path", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--model", "model_path", type=click.Path(exists=True, file_okay=False), required=True)
@click.option("--dpi", type=int, default=300, show_default=True)
@click.option("--show-tokens", is_flag=True, help="Print every non-O token with its label")
def main(pdf_path: str, model_path: str, dpi: int, show_tokens: bool) -> None:
    pdf = Path(pdf_path)
    log.info("Extracting from: %s", pdf.name)
    log.info("Using model: %s", model_path)

    import fitz
    doc = fitz.open(str(pdf))
    n_pages = doc.page_count
    doc.close()

    per_page_fields: list[dict[str, str]] = []
    all_words: list[str] = []
    for pi in range(n_pages):
        img, words, size = _render_and_extract(pdf, pi, dpi)
        log.info("Page %d: %d words", pi + 1, len(words))
        if not words:
            continue
        fields, labels, word_texts, mean_conf = _run_model(img, words, size, model_path)
        log.info("Page %d mean_conf=%.3f", pi + 1, mean_conf)
        if show_tokens:
            for w, l in zip(word_texts, labels):
                if l != "O":
                    print(f"    {l:32s} {w}")
        per_page_fields.append(fields)
        all_words.extend(word_texts)

    merged = _merge_fields(per_page_fields)
    merged = postprocess(merged, all_words)
    print()
    print("=" * 70)
    print(f"  EXTRACTED FIELDS  ({pdf.name})")
    print("=" * 70)
    print(json.dumps(merged, indent=2, ensure_ascii=False))
    print("=" * 70)


if __name__ == "__main__":
    main()
