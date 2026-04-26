from ocr_engine.ensemble.champ_challenger import ChampChallenger, _fields_agree
from ocr_engine.extraction.infer import Prediction


def _pred(fields, conf=0.9):
    return Prediction(fields=fields, mean_confidence=conf)


def test_numeric_agreement_normalizes_punctuation():
    assert _fields_agree("total_amount", "$1,234.50", "1234.50")
    assert _fields_agree("subtotal", "1234.5", "1234.50")
    assert not _fields_agree("total_amount", "100", "200")


def test_text_agreement_case_insensitive():
    assert _fields_agree("invoice_number", "INV-001", "inv-001")


def test_fuzzy_vendor_agreement():
    # Small OCR typo should still count as agreement.
    assert _fields_agree("vendor_name", "Acme Corporation", "Acme Corporatlon")


def test_auto_approve_when_all_agree():
    champ = _pred({"invoice_number": "INV-1", "total_amount": "100.00"}, conf=0.95)
    chal = _pred({"invoice_number": "INV-1", "total_amount": "100"}, conf=0.9)

    class _P:
        def __init__(self, pred): self._pred = pred
        def predict(self, _): return self._pred

    ens = ChampChallenger(_P(champ), _P(chal))
    decision = ens._decide(champ, chal)
    assert decision.decision == "AUTO_APPROVE"
    assert decision.agreement_ratio == 1.0


def test_review_required_on_mismatch():
    champ = _pred({"total_amount": "100.00"}, conf=0.9)
    chal = _pred({"total_amount": "999.99"}, conf=0.9)
    ens = ChampChallenger.__new__(ChampChallenger)
    ens.auto_approve_threshold = 0.9
    ens.min_confidence = 0.7
    d = ens._decide(champ, chal)
    assert d.decision == "REVIEW_REQUIRED"
    assert d.mismatches["total_amount"] is True


def test_low_confidence_forces_review():
    champ = _pred({"total_amount": "100.00"}, conf=0.3)
    chal = _pred({"total_amount": "100.00"}, conf=0.4)
    ens = ChampChallenger.__new__(ChampChallenger)
    ens.auto_approve_threshold = 0.9
    ens.min_confidence = 0.8
    d = ens._decide(champ, chal)
    assert d.decision == "REVIEW_REQUIRED"
