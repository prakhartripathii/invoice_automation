"""Convert raw PDF invoices to the labeled-dataset format used by train_layoutlm.

For each input PDF we:
  1. Render the page to a JPG (300 DPI by default).
  2. Extract word-level text + bboxes:
       - Preferred: PyMuPDF embedded-text extraction (instant, perfect, works
         for digitally-generated invoices).
       - Fallback: PaddleOCR (only if the PDF has no embedded text — e.g. scans).
  3. Write a sibling JSON containing {image, words, bboxes, labels, image_size}
     where every label is "O" (placeholder — auto-labeler runs next).

Usage:
    python -m ocr_engine.scripts.prepare_custom_pdfs \
        --in  ocr_engine/datasets/custom_invoices_raw \
        --out ocr_engine/datasets/custom_invoices --first-page-only
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import click

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _render_pdf(pdf_path: Path, dpi: int, first_page_only: bool):
    """Yield (page_index, PIL.Image) for each page in the PDF.

    Prefers PyMuPDF (no external binary). Falls back to pdf2image+Poppler.
    """
    # --- Preferred: PyMuPDF (self-contained) ---
    try:
        import fitz  # PyMuPDF
        from PIL import Image
        import io
        doc = fitz.open(str(pdf_path))
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        n_pages = 1 if first_page_only else doc.page_count
        for i in range(n_pages):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            yield i + 1, img
        doc.close()
        return
    except ImportError:
        pass

    # --- Fallback: pdf2image (requires Poppler) ---
    from pdf2image import convert_from_path  # type: ignore
    kwargs = {"dpi": dpi, "fmt": "jpeg"}
    if first_page_only:
        kwargs["first_page"] = 1
        kwargs["last_page"] = 1
    images = convert_from_path(str(pdf_path), **kwargs)
    for i, img in enumerate(images, start=1):
        yield i, img


def _extract_words_pymupdf(page, image_size, dpi):
    """Extract word-level text + bboxes from a PDF page using embedded text.

    Returns (words, bboxes) in image-pixel coordinates, or ([], []) if the
    page has no embedded text (e.g. it's a scanned image).
    PyMuPDF returns coords in PDF points (1pt = 1/72 inch); we scale to pixels.
    """
    raw = page.get_text("words")  # list of (x0,y0,x1,y1, word, block, line, wordno)
    if not raw:
        return [], []
    scale = dpi / 72.0
    W, H = image_size
    words: list[str] = []
    bboxes: list[list[int]] = []
    for x0, y0, x1, y1, w, *_ in raw:
        if not w or not w.strip():
            continue
        words.append(w.strip())
        bboxes.append([
            max(0, min(W, int(x0 * scale))),
            max(0, min(H, int(y0 * scale))),
            max(0, min(W, int(x1 * scale))),
            max(0, min(H, int(y1 * scale))),
        ])
    return words, bboxes


def _ocr_image_paddle(image, engine):
    """Fallback OCR for scanned PDFs (no embedded text)."""
    import numpy as np
    arr = np.array(image.convert("RGB"))
    arr_bgr = arr[:, :, ::-1].copy()
    result = engine.read(arr_bgr)
    words = [w.text for w in result.words]
    bboxes = [list(w.bbox) for w in result.words]
    return words, bboxes, result.image_size


@click.command()
@click.option("--in", "in_dir", type=click.Path(exists=True, file_okay=False),
              required=True, help="Directory containing raw .pdf files")
@click.option("--out", "out_dir", type=click.Path(file_okay=False),
              required=True, help="Where to write .jpg + .json pairs")
@click.option("--dpi", type=int, default=300, show_default=True)
@click.option("--first-page-only", is_flag=True,
              help="Only render page 1 of each PDF (most invoices are 1 page).")
def main(in_dir: str, out_dir: str, dpi: int, first_page_only: bool) -> None:
    src = Path(in_dir)
    dst = Path(out_dir)
    dst.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(src.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {src}")
    log.info("Found %d PDFs in %s", len(pdfs), src)

    import fitz  # PyMuPDF

    paddle_engine = None  # Lazy-init only if a scanned PDF needs OCR

    n_written = 0
    for pdf in pdfs:
        stem = pdf.stem.replace(" ", "_").replace(".", "_")
        try:
            doc = fitz.open(str(pdf))
            n_pages = 1 if first_page_only else doc.page_count
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            for page_idx in range(n_pages):
                page = doc.load_page(page_idx)
                page_stem = f"{stem}_p{page_idx + 1}" if not first_page_only else stem
                jpg_path = dst / f"{page_stem}.jpg"
                json_path = dst / f"{page_stem}.json"

                # Render page to JPG
                from PIL import Image
                import io as _io
                pix = page.get_pixmap(matrix=mat, alpha=False)
                image = Image.open(_io.BytesIO(pix.tobytes("png"))).convert("RGB")
                image.save(jpg_path, "JPEG", quality=92)
                W, H = image.size

                # Try PyMuPDF embedded-text extraction first
                words, bboxes = _extract_words_pymupdf(page, (W, H), dpi)
                src_method = "pymupdf"
                if not words:
                    # Fallback: PaddleOCR for scanned pages
                    if paddle_engine is None:
                        from ocr_engine.ocr.paddle_engine import PaddleOCREngine
                        paddle_engine = PaddleOCREngine(lang="en", use_gpu=False)
                    words, bboxes, (W, H) = _ocr_image_paddle(image, paddle_engine)
                    src_method = "paddleocr"
                if not words:
                    log.warning("No words extracted on %s page %d", pdf.name, page_idx + 1)

                payload = {
                    "image": jpg_path.name,
                    "words": words,
                    "bboxes": bboxes,
                    "labels": ["O"] * len(words),  # placeholders — auto-labeler fills these
                    "image_size": [W, H],
                }
                json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
                n_written += 1
                log.info("Processed %s p%d via %s → %d words",
                         pdf.name, page_idx + 1, src_method, len(words))
            doc.close()
        except Exception as e:
            log.error("Failed on %s: %s", pdf.name, e)

    log.info("Wrote %d page JSON+JPG pairs to %s", n_written, dst)
    log.info(
        "Next: label each .json (replace 'O' with B-/I- tags) "
        "via Label Studio or hand-edit, then run train_layoutlm.py."
    )


if __name__ == "__main__":
    main()
