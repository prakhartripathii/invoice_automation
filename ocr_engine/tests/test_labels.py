from ocr_engine.config.labels import BIO_LABELS, FIELD_LABELS, ID2LABEL, LABEL2ID, NUM_LABELS


def test_bio_labels_length_matches():
    assert NUM_LABELS == len(BIO_LABELS)
    assert NUM_LABELS == 1 + 2 * len(FIELD_LABELS)


def test_o_is_zero():
    assert LABEL2ID["O"] == 0


def test_roundtrip():
    for i, lbl in ID2LABEL.items():
        assert LABEL2ID[lbl] == i


def test_every_field_has_bi_pair():
    for f in FIELD_LABELS:
        assert f"B-{f.upper()}" in LABEL2ID
        assert f"I-{f.upper()}" in LABEL2ID
