import json
from pathlib import Path

import pytest

from ocr_engine.data.converters import save_internal_example, validate_example, words_to_bio


def test_words_to_bio_tags_exact_matches():
    words = ["INV-123", "Acme", "Corp", "Total", "100.00"]
    bboxes = [[0, 0, 10, 10]] * 5
    fields = {"vendor_name": "Acme Corp", "total_amount": "100.00", "invoice_number": "INV-123"}
    labels = words_to_bio(words, bboxes, fields)
    assert labels == [
        "B-INVOICE_NUMBER",
        "B-VENDOR_NAME",
        "I-VENDOR_NAME",
        "O",
        "B-TOTAL_AMOUNT",
    ]


def test_words_to_bio_handles_missing_fields():
    words = ["a", "b"]
    bboxes = [[0, 0, 1, 1], [1, 1, 2, 2]]
    assert words_to_bio(words, bboxes, {}) == ["O", "O"]


def test_validate_catches_length_mismatch():
    errs = validate_example({
        "image": "x.png",
        "words": ["a"],
        "bboxes": [[0, 0, 1, 1], [0, 0, 1, 1]],
        "labels": ["O"],
    })
    assert any("length mismatch" in e for e in errs)


def test_validate_catches_unknown_label():
    errs = validate_example({
        "image": "x.png",
        "words": ["a"],
        "bboxes": [[0, 0, 1, 1]],
        "labels": ["B-NOT_A_FIELD"],
    })
    assert any("Unknown label" in e for e in errs)


def test_save_internal_example_round_trip(tmp_path: Path):
    ex = {
        "image": "x.png",
        "words": ["a"],
        "bboxes": [[0, 0, 1, 1]],
        "labels": ["O"],
    }
    p = save_internal_example(ex, tmp_path / "x.json")
    reloaded = json.loads(p.read_text(encoding="utf-8"))
    assert reloaded["words"] == ["a"]


def test_save_rejects_invalid(tmp_path: Path):
    with pytest.raises(ValueError):
        save_internal_example({"image": "x.png"}, tmp_path / "bad.json")
