"""Bridge to Label Studio — export raw OCR'd invoices for human labeling; import corrections."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from ..config import FIELD_LABELS
from .converters import save_internal_example

log = logging.getLogger(__name__)


def export_to_label_studio(
    src_dir: str | Path,
    out_json: str | Path,
    *,
    image_url_prefix: str = "/data/upload/",
) -> int:
    """Export internal-schema JSONs → a single Label Studio tasks file.

    Serves the images via Label Studio's local storage; prefix is usually `/data/local-files/?d=...`.
    """
    src = Path(src_dir)
    tasks: list[dict[str, Any]] = []
    for jp in sorted(src.glob("*.json")):
        try:
            ex = json.loads(jp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "image" not in ex or "words" not in ex:
            continue
        tasks.append(
            {
                "data": {
                    "image": f"{image_url_prefix}{ex['image']}",
                    "words": ex["words"],
                    "bboxes": ex.get("bboxes", []),
                    "suggested_labels": ex.get("labels", []),
                },
                "meta": {"source_file": jp.name},
            }
        )
    out = Path(out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Exported %d tasks to %s", len(tasks), out)
    return len(tasks)


def import_from_label_studio(
    export_json: str | Path,
    image_dir: str | Path,
    out_dir: str | Path,
) -> int:
    """Convert a Label Studio export (JSON) into internal-schema files.

    Expected labeling config: RectangleLabels over image with one label per FIELD_LABELS entry.
    """
    export = json.loads(Path(export_json).read_text(encoding="utf-8"))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    img_dir = Path(image_dir)

    count = 0
    allowed_fields = {f.upper() for f in FIELD_LABELS}
    for task in export:
        data = task.get("data", {}) or {}
        img_ref = data.get("image") or data.get("ocr") or ""
        img_name = Path(str(img_ref)).name
        src_img = img_dir / img_name
        if not src_img.exists():
            log.warning("Image not found for task: %s", img_name)
            continue

        annotations = task.get("annotations") or task.get("completions") or []
        if not annotations:
            continue
        ann = annotations[0]
        results = ann.get("result", [])

        # Collect rectangles + label per box, then map to word-level via OCR words if present.
        words: list[str] = data.get("words", []) or []
        bboxes_in: list[list[int]] = data.get("bboxes", []) or []
        labels = ["O"] * len(words)

        for r in results:
            val = r.get("value", {})
            rect_labels = val.get("rectanglelabels") or val.get("labels") or []
            if not rect_labels:
                continue
            field = str(rect_labels[0]).upper()
            if field not in allowed_fields:
                continue
            # Label Studio returns x/y/width/height as % of image size.
            orig_w = r.get("original_width") or 1
            orig_h = r.get("original_height") or 1
            x = val.get("x", 0) / 100.0 * orig_w
            y = val.get("y", 0) / 100.0 * orig_h
            w = val.get("width", 0) / 100.0 * orig_w
            h = val.get("height", 0) / 100.0 * orig_h
            rect = (x, y, x + w, y + h)
            started = False
            for i, wb in enumerate(bboxes_in):
                if _box_inside(wb, rect, tol=0.5):
                    labels[i] = f"{'B' if not started else 'I'}-{field}"
                    started = True

        dst_img = out / img_name
        shutil.copy2(src_img, dst_img)
        save_internal_example(
            {
                "image": img_name,
                "words": words,
                "bboxes": bboxes_in,
                "labels": labels,
            },
            out / f"{src_img.stem}.json",
        )
        count += 1
    log.info("Imported %d label-studio annotations → %s", count, out)
    return count


def _box_inside(inner: list[int], outer: tuple[float, float, float, float], tol: float = 0.5) -> bool:
    ix0, iy0, ix1, iy1 = inner
    ox0, oy0, ox1, oy1 = outer
    cx = (ix0 + ix1) / 2
    cy = (iy0 + iy1) / 2
    # Require centroid inside with `tol` margin — tolerates slight label mis-draws.
    mx = (ox1 - ox0) * tol * 0.25
    my = (oy1 - oy0) * tol * 0.25
    return (ox0 - mx) <= cx <= (ox1 + mx) and (oy0 - my) <= cy <= (oy1 + my)
