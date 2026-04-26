"""Token-level metrics (seqeval) for LayoutLMv3 training."""
from __future__ import annotations

import logging
from typing import Any

from ..config import ID2LABEL

log = logging.getLogger(__name__)


def compute_token_metrics(eval_pred: Any) -> dict[str, float]:
    """Hugging Face Trainer-compatible metric callback."""
    try:
        import numpy as np
        from seqeval.metrics import classification_report, f1_score, precision_score, recall_score
    except ImportError as e:
        raise ImportError("seqeval + numpy required for metrics") from e

    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=-1)
    true_preds: list[list[str]] = []
    true_labels: list[list[str]] = []
    for pred_row, label_row in zip(predictions, labels):
        p_seq: list[str] = []
        l_seq: list[str] = []
        for p, l in zip(pred_row, label_row):
            if l == -100:
                continue
            p_seq.append(ID2LABEL.get(int(p), "O"))
            l_seq.append(ID2LABEL.get(int(l), "O"))
        if p_seq:
            true_preds.append(p_seq)
            true_labels.append(l_seq)

    if not true_labels:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    try:
        report = classification_report(true_labels, true_preds, zero_division=0)
        log.info("\n%s", report)
    except Exception as e:  # pragma: no cover
        log.debug("classification_report failed: %s", e)

    return {
        "precision": float(precision_score(true_labels, true_preds, zero_division=0)),
        "recall": float(recall_score(true_labels, true_preds, zero_division=0)),
        "f1": float(f1_score(true_labels, true_preds, zero_division=0)),
    }
