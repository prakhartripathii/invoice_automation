"""Ingest human corrections from the review queue back into training data."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from ..data.converters import save_internal_example, words_to_bio
from ..ocr.paddle_engine import PaddleOCREngine
from ..preprocessing import preprocess_for_ocr

log = logging.getLogger(__name__)


class FeedbackIngestor:
    """Turn (invoice_image, human-corrected-fields) pairs into labeled training data.

    Call this from the backend after a reviewer clicks Approve — it re-runs OCR to get
    word boxes, then BIO-tags the words using the verified field values.
    """

    def __init__(self, out_dir: str | Path, ocr=None) -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.ocr = ocr or PaddleOCREngine()
        self.manifest = self.out_dir / "manifest.jsonl"

    def ingest(self, sample_id: str, field_values: dict[str, str], image_path: str | Path) -> Path:
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(image_path)

        img = preprocess_for_ocr(image_path, do_deskew=True, do_denoise=True)
        ocr_res = self.ocr.read(img)
        if not ocr_res.words:
            raise RuntimeError(f"OCR returned no words for {image_path}")

        words = [w.text for w in ocr_res.words]
        bboxes = [list(w.bbox) for w in ocr_res.words]
        labels = words_to_bio(words, bboxes, field_values)

        # Copy image alongside the JSON so the dataset loader can find it.
        dst_img = self.out_dir / f"{sample_id}{image_path.suffix.lower()}"
        shutil.copy2(image_path, dst_img)

        json_path = self.out_dir / f"{sample_id}.json"
        save_internal_example(
            {
                "image": dst_img.name,
                "words": words,
                "bboxes": bboxes,
                "labels": labels,
                "image_size": list(ocr_res.image_size),
                "source": "human_correction",
            },
            json_path,
        )

        self._append_manifest({"sample_id": sample_id, "json": json_path.name, "fields": field_values})
        log.info("Ingested correction for %s", sample_id)
        return json_path

    def _append_manifest(self, entry: dict[str, Any]) -> None:
        with self.manifest.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def count(self) -> int:
        return len(list(self.out_dir.glob("*.json")))
