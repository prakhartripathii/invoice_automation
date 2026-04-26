"""Converters for public datasets → our internal schema.

We do not bundle the datasets (licenses / size). The functions below take a folder
that the user already downloaded and emit our standard JSON-per-invoice format.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from .converters import save_internal_example, words_to_bio

log = logging.getLogger(__name__)

# ---------- SROIE ----------
# Folder layout (download from https://rrc.cvc.uab.es/?ch=13):
#   sroie/img/X51005200938.jpg
#   sroie/box/X51005200938.txt    (one line per text box: x1,y1,x2,y2,x3,y3,x4,y4,text)
#   sroie/entities/X51005200938.txt  ({"company":..., "date":..., "address":..., "total":...})


def convert_sroie(src_dir: str | Path, out_dir: str | Path) -> int:
    src, out = Path(src_dir), Path(out_dir)
    img_dir, box_dir, ent_dir = src / "img", src / "box", src / "entities"
    if not all(p.exists() for p in (img_dir, box_dir, ent_dir)):
        raise FileNotFoundError(f"SROIE structure not found under {src}. Expected img/, box/, entities/")
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    sroie_to_field = {
        "company": "vendor_name",
        "address": "vendor_address",
        "date": "invoice_date",
        "total": "total_amount",
    }
    for img_path in sorted(img_dir.glob("*.jpg")):
        stem = img_path.stem
        box_path = box_dir / f"{stem}.txt"
        ent_path = ent_dir / f"{stem}.txt"
        if not box_path.exists() or not ent_path.exists():
            continue
        try:
            entities: dict[str, str] = json.loads(ent_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Bad entities for %s: %s", stem, e)
            continue
        words, bboxes = _parse_sroie_boxes(box_path)
        if not words:
            continue
        field_values = {sroie_to_field[k]: v for k, v in entities.items() if k in sroie_to_field}
        labels = words_to_bio(words, bboxes, field_values)
        dst_img = out / img_path.name
        shutil.copy2(img_path, dst_img)
        save_internal_example(
            {
                "image": img_path.name,
                "words": words,
                "bboxes": bboxes,
                "labels": labels,
            },
            out / f"{stem}.json",
        )
        count += 1
    log.info("SROIE: wrote %d examples to %s", count, out)
    return count


def _parse_sroie_boxes(path: Path) -> tuple[list[str], list[list[int]]]:
    words: list[str] = []
    bboxes: list[list[int]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split(",", 8)
        if len(parts) < 9:
            continue
        try:
            coords = [int(float(x)) for x in parts[:8]]
        except ValueError:
            continue
        text = parts[8].strip()
        if not text:
            continue
        xs, ys = coords[0::2], coords[1::2]
        bbox = [min(xs), min(ys), max(xs), max(ys)]
        for tok in text.split():
            words.append(tok)
            bboxes.append(bbox)
    return words, bboxes


# ---------- FUNSD ----------
# Download: https://guillaumejaume.github.io/FUNSD/
# Layout: funsd/training_data/{annotations,images} and testing_data.

def convert_funsd(src_dir: str | Path, out_dir: str | Path) -> int:
    src, out = Path(src_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    for split_dir in (src / "training_data", src / "testing_data"):
        ann_dir = split_dir / "annotations"
        img_dir = split_dir / "images"
        if not (ann_dir.exists() and img_dir.exists()):
            continue
        for ann_path in sorted(ann_dir.glob("*.json")):
            try:
                ann = json.loads(ann_path.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning("Skipping %s: %s", ann_path, e)
                continue
            img_name = ann_path.stem + ".png"
            img_path = img_dir / img_name
            if not img_path.exists():
                continue
            words, bboxes, labels = [], [], []
            for form in ann.get("form", []):
                for tok in form.get("words", []):
                    text = (tok.get("text") or "").strip()
                    if not text:
                        continue
                    box = tok.get("box")
                    if not box or len(box) != 4:
                        continue
                    words.append(text)
                    bboxes.append([int(v) for v in box])
                    # FUNSD labels are question/answer/header/other — we tag everything as O
                    # so the model learns layout primitives but not field semantics.
                    labels.append("O")
            if not words:
                continue
            dst_img = out / img_name
            shutil.copy2(img_path, dst_img)
            save_internal_example(
                {"image": img_name, "words": words, "bboxes": bboxes, "labels": labels},
                out / f"{ann_path.stem}.json",
            )
            count += 1
    log.info("FUNSD: wrote %d examples to %s", count, out)
    return count


# ---------- CORD ----------
# Download: https://github.com/clovaai/cord  (JSON with receipts and line items)

CORD_FIELD_MAP = {
    "menu.nm": "line_item_description",
    "menu.cnt": "line_item_quantity",
    "menu.price": "line_item_amount",
    "menu.unitprice": "line_item_unit_price",
    "total.total_price": "total_amount",
    "total.subtotal_price": "subtotal",
    "total.tax_price": "tax_amount",
    "sub_total.subtotal_price": "subtotal",
    "sub_total.tax_price": "tax_amount",
}


def convert_cord(src_dir: str | Path, out_dir: str | Path) -> int:
    src, out = Path(src_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    for split in ("train", "dev", "test"):
        split_dir = src / split
        img_dir = split_dir / "image"
        json_dir = split_dir / "json"
        if not (img_dir.exists() and json_dir.exists()):
            continue
        for jp in sorted(json_dir.glob("*.json")):
            try:
                data = json.loads(jp.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning("Skipping %s: %s", jp, e)
                continue
            img_name = jp.stem + ".png"
            img_path = img_dir / img_name
            if not img_path.exists():
                img_path = img_dir / (jp.stem + ".jpg")
                img_name = img_path.name
            if not img_path.exists():
                continue
            words, bboxes, labels = _flatten_cord(data)
            if not words:
                continue
            dst = out / img_name
            shutil.copy2(img_path, dst)
            save_internal_example(
                {"image": img_name, "words": words, "bboxes": bboxes, "labels": labels},
                out / f"{jp.stem}.json",
            )
            count += 1
    log.info("CORD: wrote %d examples to %s", count, out)
    return count


def _flatten_cord(data: dict[str, Any]) -> tuple[list[str], list[list[int]], list[str]]:
    words: list[str] = []
    bboxes: list[list[int]] = []
    labels: list[str] = []
    for line in data.get("valid_line", []):
        category = line.get("category", "")
        for w in line.get("words", []):
            text = (w.get("text") or "").strip()
            if not text:
                continue
            q = w.get("quad") or {}
            try:
                xs = [q["x1"], q["x2"], q["x3"], q["x4"]]
                ys = [q["y1"], q["y2"], q["y3"], q["y4"]]
            except KeyError:
                continue
            box = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
            field = CORD_FIELD_MAP.get(category)
            if field:
                tag = f"{'B' if not labels or not labels[-1].endswith(field.upper()) else 'I'}-{field.upper()}"
            else:
                tag = "O"
            words.append(text)
            bboxes.append(box)
            labels.append(tag)
    return words, bboxes, labels
