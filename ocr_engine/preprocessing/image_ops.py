"""Image preprocessing for OCR: deskew, denoise, binarize, auto-orient."""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Union

import numpy as np

log = logging.getLogger(__name__)

ImageLike = Union[str, Path, bytes, np.ndarray]


def _require_cv2():
    try:
        import cv2  # type: ignore

        return cv2
    except ImportError as e:
        raise ImportError(
            "opencv-python-headless is required. Install via `pip install opencv-python-headless`."
        ) from e


def load_image(src: ImageLike) -> np.ndarray:
    """Load an image from disk path, bytes, or pass-through ndarray. Returns BGR uint8."""
    cv2 = _require_cv2()
    if isinstance(src, np.ndarray):
        return src
    if isinstance(src, (bytes, bytearray)):
        arr = np.frombuffer(src, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image from bytes.")
        return img
    path = Path(src)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"OpenCV failed to read: {path}")
    return img


def to_grayscale(img: np.ndarray) -> np.ndarray:
    cv2 = _require_cv2()
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def denoise(img: np.ndarray, strength: int = 10) -> np.ndarray:
    """Fast non-local means denoising. Works on grayscale or BGR."""
    cv2 = _require_cv2()
    if img.ndim == 2:
        return cv2.fastNlMeansDenoising(img, h=strength)
    return cv2.fastNlMeansDenoisingColored(img, h=strength, hColor=strength)


def deskew(img: np.ndarray, max_angle: float = 15.0) -> np.ndarray:
    """Estimate skew via minAreaRect on dark pixels and rotate. Clamps rotation to ±max_angle."""
    cv2 = _require_cv2()
    gray = to_grayscale(img)
    # Invert so text is foreground
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(bw > 0))
    if coords.size == 0:
        return img
    angle = cv2.minAreaRect(coords)[-1]
    # cv2 returns angle in [-90, 0); normalize to small rotation around 0
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) > max_angle:
        log.debug("Skew angle %.2f exceeds max %.2f; skipping rotation", angle, max_angle)
        return img
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def binarize_sauvola(img: np.ndarray, window: int = 25, k: float = 0.2) -> np.ndarray:
    """Sauvola adaptive threshold — robust to uneven lighting on scans."""
    try:
        from skimage.filters import threshold_sauvola  # type: ignore
    except ImportError as e:
        raise ImportError("scikit-image is required for binarize_sauvola") from e
    gray = to_grayscale(img)
    if window % 2 == 0:
        window += 1
    thresh = threshold_sauvola(gray, window_size=window, k=k)
    binary = (gray > thresh).astype(np.uint8) * 255
    return binary


def auto_orient(img: np.ndarray) -> np.ndarray:
    """Correct 90/180/270° rotation using Tesseract OSD if available. No-op if not installed."""
    try:
        import pytesseract  # type: ignore
    except ImportError:
        return img
    try:
        osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)
        rot = int(osd.get("rotate", 0))
    except Exception as e:  # pragma: no cover
        log.debug("OSD failed: %s", e)
        return img
    if rot == 0:
        return img
    cv2 = _require_cv2()
    rot_map = {
        90: cv2.ROTATE_90_COUNTERCLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_CLOCKWISE,
    }
    code = rot_map.get(rot)
    return cv2.rotate(img, code) if code is not None else img


def preprocess_for_ocr(
    src: ImageLike,
    *,
    do_deskew: bool = True,
    do_denoise: bool = True,
    do_binarize: bool = False,
    do_orient: bool = False,
) -> np.ndarray:
    """Full pipeline. Returns BGR or grayscale image ready for OCR."""
    img = load_image(src)
    if do_orient:
        img = auto_orient(img)
    if do_denoise:
        img = denoise(img)
    if do_deskew:
        img = deskew(img)
    if do_binarize:
        img = binarize_sauvola(img)
    return img
