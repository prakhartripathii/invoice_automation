import numpy as np
import pytest


@pytest.fixture
def dummy_image():
    # 100x80 gradient, 3-channel uint8
    return (np.tile(np.arange(100, dtype=np.uint8), (80, 1))[..., None].repeat(3, axis=-1))


def test_to_grayscale_shape(dummy_image):
    pytest.importorskip("cv2")
    from ocr_engine.preprocessing.image_ops import to_grayscale

    g = to_grayscale(dummy_image)
    assert g.ndim == 2
    assert g.shape == (80, 100)


def test_deskew_returns_same_shape(dummy_image):
    pytest.importorskip("cv2")
    from ocr_engine.preprocessing.image_ops import deskew

    out = deskew(dummy_image)
    assert out.shape == dummy_image.shape


def test_load_image_missing_path(tmp_path):
    pytest.importorskip("cv2")
    from ocr_engine.preprocessing.image_ops import load_image

    with pytest.raises(FileNotFoundError):
        load_image(tmp_path / "does_not_exist.png")


def test_denoise_shape(dummy_image):
    pytest.importorskip("cv2")
    from ocr_engine.preprocessing.image_ops import denoise

    out = denoise(dummy_image)
    assert out.shape == dummy_image.shape
