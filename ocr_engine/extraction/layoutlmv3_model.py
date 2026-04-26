"""Load / save LayoutLMv3 token-classification model + processor."""
from __future__ import annotations

import logging
from pathlib import Path

from ..config import ID2LABEL, LABEL2ID, NUM_LABELS, get_settings

log = logging.getLogger(__name__)


def load_processor(model_name_or_path: str | Path | None = None):
    try:
        from transformers import LayoutLMv3Processor  # type: ignore
    except ImportError as e:
        raise ImportError("transformers is required. `pip install transformers`") from e
    name = str(model_name_or_path or get_settings().base_model_name)
    # apply_ocr=False — we supply our own words + boxes from PaddleOCR.
    return LayoutLMv3Processor.from_pretrained(name, apply_ocr=False)


def load_model(model_name_or_path: str | Path | None = None, num_labels: int | None = None):
    try:
        from transformers import LayoutLMv3ForTokenClassification  # type: ignore
    except ImportError as e:
        raise ImportError("transformers is required. `pip install transformers`") from e
    name = str(model_name_or_path or get_settings().base_model_name)
    n = num_labels if num_labels is not None else NUM_LABELS
    return LayoutLMv3ForTokenClassification.from_pretrained(
        name,
        num_labels=n,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True,
    )


def save_artifacts(model, processor, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    processor.save_pretrained(out)
    log.info("Saved model + processor to %s", out)
    return out
