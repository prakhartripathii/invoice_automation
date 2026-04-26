"""Uncertainty scoring for active learning — pick the hardest predictions to relabel first."""
from __future__ import annotations

import math
from typing import Sequence

from ..extraction.infer import Prediction


def _entropy(probs: Sequence[float]) -> float:
    h = 0.0
    for p in probs:
        if p > 0:
            h -= p * math.log(p)
    return h


def score_uncertainty(pred: Prediction, strategy: str = "entropy") -> float:
    """Higher score = more uncertain = better candidate for human labeling."""
    if not pred.token_confidences:
        return 1.0
    confs = [max(1e-6, min(1.0 - 1e-6, c)) for c in pred.token_confidences]
    if strategy == "margin":
        # 1 - avg confidence — confident models get low scores.
        return 1.0 - sum(confs) / len(confs)
    if strategy == "min_conf":
        return 1.0 - min(confs)
    # default: entropy-like, using confidence as p and (1-p) as residual
    hs = [_entropy([c, 1 - c]) for c in confs]
    return sum(hs) / len(hs)


def pick_top_uncertain(
    preds: Sequence[tuple[str, Prediction]],
    k: int,
    strategy: str = "entropy",
) -> list[tuple[str, Prediction, float]]:
    """Given (id, prediction) pairs, return the top-k most uncertain with their score."""
    scored = [(sid, p, score_uncertainty(p, strategy)) for sid, p in preds]
    scored.sort(key=lambda t: t[2], reverse=True)
    return scored[: max(0, k)]
