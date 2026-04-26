"""Champ/Challenger ensemble — auto-approve only when both predictors agree."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from ..extraction.infer import InvoicePredictor, Prediction

log = logging.getLogger(__name__)


# Fields where exact-match is too strict: small OCR typos shouldn't kill agreement.
FUZZY_FIELDS = {"vendor_name", "vendor_address", "line_item_description"}
# Numeric fields: compare after normalizing currency symbols, commas, spaces.
NUMERIC_FIELDS = {
    "subtotal",
    "tax_amount",
    "total_amount",
    "line_item_unit_price",
    "line_item_amount",
    "line_item_quantity",
}


@dataclass
class EnsembleDecision:
    decision: str  # AUTO_APPROVE | REVIEW_REQUIRED | REJECT
    fields: dict[str, str] = field(default_factory=dict)
    champ_fields: dict[str, str] = field(default_factory=dict)
    challenger_fields: dict[str, str] = field(default_factory=dict)
    agreement_ratio: float = 0.0
    weighted_confidence: float = 0.0
    mismatches: dict[str, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "fields": self.fields,
            "champ_fields": self.champ_fields,
            "challenger_fields": self.challenger_fields,
            "agreement_ratio": self.agreement_ratio,
            "weighted_confidence": self.weighted_confidence,
            "mismatches": self.mismatches,
            "reasons": self.reasons,
        }


def _normalize_numeric(v: str) -> str | None:
    if v is None:
        return None
    stripped = re.sub(r"[^\d.\-]", "", v)
    try:
        return f"{float(stripped):.2f}"
    except ValueError:
        return None


def _normalize_text(v: str) -> str:
    return re.sub(r"\s+", " ", (v or "").strip()).lower()


def _fuzzy_equal(a: str, b: str, threshold: float = 0.7) -> bool:
    a, b = _normalize_text(a), _normalize_text(b)
    if not a or not b:
        return a == b
    if a == b:
        return True
    # Simple Jaccard on char-trigrams — dependency-free and good enough for near-duplicates.
    def trigrams(s: str) -> set[str]:
        s = f"  {s}  "
        return {s[i : i + 3] for i in range(len(s) - 2)}

    ta, tb = trigrams(a), trigrams(b)
    if not ta or not tb:
        return False
    j = len(ta & tb) / max(1, len(ta | tb))
    return j >= threshold


def _fields_agree(key: str, a: str | None, b: str | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if key in NUMERIC_FIELDS:
        return _normalize_numeric(a) == _normalize_numeric(b) and _normalize_numeric(a) is not None
    if key in FUZZY_FIELDS:
        return _fuzzy_equal(a, b)
    return _normalize_text(a) == _normalize_text(b)


class ChampChallenger:
    """Run two predictors and agree-or-escalate."""

    def __init__(
        self,
        champ: InvoicePredictor,
        challenger: InvoicePredictor,
        *,
        auto_approve_threshold: float = 0.9,
        min_confidence: float = 0.75,
    ) -> None:
        self.champ = champ
        self.challenger = challenger
        self.auto_approve_threshold = auto_approve_threshold
        self.min_confidence = min_confidence

    def predict(self, image_src: Any) -> EnsembleDecision:
        p_champ = self.champ.predict(image_src)
        p_chal = self.challenger.predict(image_src)
        return self._decide(p_champ, p_chal)

    def _decide(self, champ: Prediction, challenger: Prediction) -> EnsembleDecision:
        all_keys = set(champ.fields) | set(challenger.fields)
        matches = 0
        mismatches: dict[str, bool] = {}
        merged: dict[str, str] = {}

        for k in sorted(all_keys):
            a = champ.fields.get(k)
            b = challenger.fields.get(k)
            if _fields_agree(k, a, b):
                matches += 1
                mismatches[k] = False
                merged[k] = a or b or ""
            else:
                mismatches[k] = True
                # Prefer the higher-confidence engine's value in the merged output.
                merged[k] = (
                    a if champ.mean_confidence >= challenger.mean_confidence else b
                ) or ""

        total = max(1, len(all_keys))
        agreement = matches / total
        weighted_conf = (champ.mean_confidence + challenger.mean_confidence) / 2.0

        reasons: list[str] = []
        if not all_keys:
            decision = "REVIEW_REQUIRED"
            reasons.append("Both engines returned no fields.")
        elif agreement >= self.auto_approve_threshold and weighted_conf >= self.min_confidence:
            decision = "AUTO_APPROVE"
        elif agreement < 0.5:
            decision = "REVIEW_REQUIRED"
            reasons.append(f"Low agreement: {agreement:.0%}")
        else:
            decision = "REVIEW_REQUIRED"
            if weighted_conf < self.min_confidence:
                reasons.append(f"Low confidence: {weighted_conf:.2f}")
            if any(mismatches.values()):
                bad = [k for k, v in mismatches.items() if v]
                reasons.append(f"Mismatches on: {', '.join(bad)}")

        return EnsembleDecision(
            decision=decision,
            fields=merged,
            champ_fields=dict(champ.fields),
            challenger_fields=dict(challenger.fields),
            agreement_ratio=agreement,
            weighted_confidence=weighted_conf,
            mismatches=mismatches,
            reasons=reasons,
        )
