"""Persistent OCR sidecar — keeps LayoutLMv3 loaded in memory.

Eliminates the ~5-10s per-invoice cost of subprocess startup + torch import +
model load. Backend posts the raw PDF bytes; we run the same pipeline as
`extract_pdf.py` (which we import) and return the field JSON.

Run:
    D:\\invoice_mgnt\\Invoice-Automation-Backend\\ocr_engine\\.venv\\Scripts\\python.exe ^
        -m ocr_engine.scripts.serve --model D:\\invoice_artifacts\\champ-v2-resumed

Endpoints:
    GET  /health      -> {"status": "ok", "model": "..."}
    POST /extract     -> JSON fields (PDF bytes in body, ?dpi=300 optional)
"""
from __future__ import annotations

import argparse
import io
import logging
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ocr_engine.scripts.extract_pdf import (
    _load_model,
    _merge_fields,
    _render_and_extract,
    _run_model,
    postprocess,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ocr_sidecar")

app = FastAPI(title="OCR Engine Sidecar")
_MODEL_PATH: str = ""


@app.on_event("startup")
def _warm_up() -> None:
    log.info("Warming up model from %s", _MODEL_PATH)
    _load_model(_MODEL_PATH)
    log.info("Model loaded — ready to serve.")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": _MODEL_PATH}


@app.post("/extract")
async def extract(request: Request, dpi: int = Query(300)) -> JSONResponse:
    body = await request.body()
    if not body:
        raise HTTPException(400, "empty body")

    # Persist to a temp file because PyMuPDF needs a path/stream.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(body)
        tmp_path = Path(tmp.name)
    try:
        import fitz
        doc = fitz.open(str(tmp_path))
        n_pages = doc.page_count
        doc.close()

        per_page_fields: list[dict[str, str]] = []
        all_words: list[str] = []
        confs: list[float] = []
        for pi in range(n_pages):
            img, words, size = _render_and_extract(tmp_path, pi, dpi)
            if not words:
                continue
            fields, _, word_texts, mc = _run_model(img, words, size, _MODEL_PATH)
            confs.append(mc)
            per_page_fields.append(fields)
            all_words.extend(word_texts)

        merged = _merge_fields(per_page_fields)
        merged = postprocess(merged, all_words)
        merged["__mean_confidence"] = sum(confs) / len(confs) if confs else 0.0
        return JSONResponse(merged)
    except Exception as e:
        log.exception("extract_failed")
        raise HTTPException(500, f"extract failed: {e}") from e
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def main() -> None:
    global _MODEL_PATH
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True, help="Path to fine-tuned LayoutLMv3 model dir")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8077)
    args = p.parse_args()
    _MODEL_PATH = args.model
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
