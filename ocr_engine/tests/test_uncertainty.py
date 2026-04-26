from ocr_engine.active_learning.uncertainty import pick_top_uncertain, score_uncertainty
from ocr_engine.extraction.infer import Prediction


def test_zero_tokens_is_maximally_uncertain():
    p = Prediction()
    assert score_uncertainty(p) == 1.0


def test_confident_prediction_has_low_uncertainty():
    high = Prediction(token_confidences=[0.99, 0.99, 0.99])
    low = Prediction(token_confidences=[0.5, 0.5, 0.5])
    assert score_uncertainty(high) < score_uncertainty(low)


def test_margin_strategy_monotonic():
    p1 = Prediction(token_confidences=[0.9])
    p2 = Prediction(token_confidences=[0.6])
    assert score_uncertainty(p1, "margin") < score_uncertainty(p2, "margin")


def test_pick_top_uncertain_orders_by_score():
    samples = [
        ("a", Prediction(token_confidences=[0.99])),
        ("b", Prediction(token_confidences=[0.5])),
        ("c", Prediction(token_confidences=[0.7])),
    ]
    top = pick_top_uncertain(samples, k=2)
    ids = [t[0] for t in top]
    assert ids[0] == "b"
    assert "c" in ids
