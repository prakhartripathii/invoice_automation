"""Internal JSON schema writer + validator + heuristic BIO tagger for weakly-labeled data."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _bio_set() -> set[str]:
    from ..config import LABEL2ID

    return set(LABEL2ID.keys())


def validate_example(ex: dict[str, Any]) -> list[str]:
    """Return list of validation errors (empty if valid)."""
    errs: list[str] = []
    required = ("image", "words", "bboxes", "labels")
    for r in required:
        if r not in ex:
            errs.append(f"Missing key: {r}")
    if errs:
        return errs
    if not (len(ex["words"]) == len(ex["bboxes"]) == len(ex["labels"])):
        errs.append("words/bboxes/labels length mismatch")
    for b in ex["bboxes"]:
        if not (isinstance(b, (list, tuple)) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b)):
            errs.append(f"Invalid bbox: {b}")
            break
    allowed = _bio_set()
    for lbl in ex["labels"]:
        if lbl not in allowed:
            errs.append(f"Unknown label: {lbl}")
            break
    return errs


def save_internal_example(ex: dict[str, Any], out_json: str | Path) -> Path:
    errs = validate_example(ex)
    if errs:
        raise ValueError(f"Invalid example: {errs}")
    p = Path(out_json)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ex, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def words_to_bio(
    words: list[str],
    bboxes: list[list[int]],
    field_values: dict[str, str],
) -> list[str]:
    """Heuristic BIO-tagging: scan OCR words for contiguous runs that match each field value.

    Used for weak labeling of public datasets (SROIE, CORD) and synthetic data.
    """
    labels = ["O"] * len(words)
    lower = [w.lower().strip() for w in words]
    for field_name, value in field_values.items():
        if not value:
            continue
        target_tokens = [t.lower().strip() for t in str(value).split() if t.strip()]
        if not target_tokens:
            continue
        tag = field_name.upper()
        n = len(target_tokens)
        i = 0
        while i <= len(lower) - n:
            if labels[i] != "O":
                i += 1
                continue
            window = lower[i : i + n]
            if all(_loose_eq(a, b) for a, b in zip(window, target_tokens)):
                labels[i] = f"B-{tag}"
                for j in range(1, n):
                    labels[i + j] = f"I-{tag}"
                i += n
            else:
                i += 1
    return labels


def _loose_eq(a: str, b: str) -> bool:
    # Ignore trailing punctuation ("Acme," vs "Acme").
    trim = ",.:;()[]{}"
    return a.strip(trim) == b.strip(trim)
