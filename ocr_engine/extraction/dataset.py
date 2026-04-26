"""Torch Dataset converting our internal JSON schema into LayoutLMv3 inputs.

Internal schema (one JSON file per invoice, stored next to the image):
{
    "image": "xyz.png",                # relative path
    "words": ["Vendor", "Acme", ...],
    "bboxes": [[x0,y0,x1,y1], ...],    # pixel coords; normalized to 0-1000 inside
    "labels": ["B-VENDOR_NAME", "I-VENDOR_NAME", ...],
    "image_size": [W, H]
}
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..config import LABEL2ID

log = logging.getLogger(__name__)


def _normalize_bbox(box: list[int], width: int, height: int, target: int = 1000) -> list[int]:
    if width <= 0 or height <= 0:
        return [0, 0, 0, 0]
    x0, y0, x1, y1 = box
    return [
        max(0, min(target, int(x0 / width * target))),
        max(0, min(target, int(y0 / height * target))),
        max(0, min(target, int(x1 / width * target))),
        max(0, min(target, int(y1 / height * target))),
    ]


class InvoiceLayoutDataset:
    """Loads labeled invoices and tokenizes them via a LayoutLMv3Processor."""

    def __init__(self, examples: list[dict[str, Any]], processor, max_length: int = 512) -> None:
        self.examples = examples
        self.processor = processor
        self.max_length = max_length

    @classmethod
    def from_directory(cls, data_dir: str | Path, processor, max_length: int = 512) -> "InvoiceLayoutDataset":
        root = Path(data_dir)
        if not root.exists():
            raise FileNotFoundError(f"Data dir does not exist: {root}")
        items: list[dict[str, Any]] = []
        for jf in sorted(root.rglob("*.json")):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                log.warning("Skipping malformed JSON %s: %s", jf, e)
                continue
            required = {"image", "words", "bboxes", "labels"}
            if not required.issubset(data):
                log.warning("Skipping %s (missing keys)", jf)
                continue
            if not (len(data["words"]) == len(data["bboxes"]) == len(data["labels"])):
                log.warning("Skipping %s (length mismatch)", jf)
                continue
            img_path = (jf.parent / data["image"]).resolve()
            if not img_path.exists():
                log.warning("Skipping %s (image not found: %s)", jf, img_path)
                continue
            data["_image_path"] = str(img_path)
            items.append(data)
        if not items:
            raise RuntimeError(f"No valid labeled examples found under {root}")
        log.info("Loaded %d labeled invoices from %s", len(items), root)
        return cls(items, processor, max_length)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int):
        from PIL import Image  # lazy import

        ex = self.examples[idx]
        image = Image.open(ex["_image_path"]).convert("RGB")
        w, h = image.size
        # If boxes are already normalized 0..1000 we leave them; otherwise normalize.
        # Check ALL bboxes, not just the first — a word in the top-left can have
        # small coords while later words exceed 1000, breaking LayoutLMv3's range check.
        bboxes = ex["bboxes"]
        needs_normalize = w > 1000 or h > 1000 or any(
            v < 0 or v > 1000 for b in bboxes for v in b
        )
        if needs_normalize:
            bboxes = [_normalize_bbox(b, w, h) for b in bboxes]

        word_labels = [LABEL2ID.get(lbl, LABEL2ID["O"]) for lbl in ex["labels"]]

        encoding = self.processor(
            image,
            ex["words"],
            boxes=bboxes,
            word_labels=word_labels,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        # Squeeze batch dim added by processor
        return {k: v.squeeze(0) for k, v in encoding.items()}


def split_dataset(ds: InvoiceLayoutDataset, eval_ratio: float = 0.1, seed: int = 42):
    import random

    rng = random.Random(seed)
    n = len(ds)
    idx = list(range(n))
    rng.shuffle(idx)
    k = max(1, int(n * eval_ratio)) if n > 1 else 0
    eval_idx, train_idx = idx[:k], idx[k:]
    train = InvoiceLayoutDataset([ds.examples[i] for i in train_idx], ds.processor, ds.max_length)
    evald = InvoiceLayoutDataset([ds.examples[i] for i in eval_idx], ds.processor, ds.max_length)
    return train, evald
