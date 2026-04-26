from ocr_engine.ocr.base import OCRResult, OCRWord


def test_ocr_word_dimensions():
    w = OCRWord(text="hi", bbox=(10, 20, 50, 40), confidence=0.9)
    assert w.width == 40
    assert w.height == 20


def test_normalized_bboxes_scale_to_1000():
    r = OCRResult(
        words=[OCRWord("a", (0, 0, 100, 100)), OCRWord("b", (100, 100, 200, 200))],
        image_size=(200, 200),
    )
    nb = r.normalized_bboxes(1000)
    assert nb == [[0, 0, 500, 500], [500, 500, 1000, 1000]]


def test_normalized_bboxes_handle_zero_size():
    r = OCRResult(words=[OCRWord("a", (0, 0, 1, 1))], image_size=(0, 0))
    assert r.normalized_bboxes() == [[0, 0, 0, 0]]


def test_texts_and_bboxes_accessors():
    r = OCRResult(
        words=[OCRWord("a", (1, 2, 3, 4)), OCRWord("b", (5, 6, 7, 8))],
        image_size=(100, 100),
    )
    assert r.texts == ["a", "b"]
    assert r.bboxes == [(1, 2, 3, 4), (5, 6, 7, 8)]
