"""PaddleOCR wrapper. Lazy-imports paddleocr so test imports stay cheap."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import numpy as np

from .base import OCREngine, OCRResult, OCRWord

log = logging.getLogger(__name__)


def _poly_to_bbox(poly: Any) -> tuple[int, int, int, int]:
    """Convert a 4-point polygon (as returned by PaddleOCR) to an axis-aligned bbox."""
    pts = np.asarray(poly, dtype=np.float32).reshape(-1, 2)
    x0 = int(np.floor(pts[:, 0].min()))
    y0 = int(np.floor(pts[:, 1].min()))
    x1 = int(np.ceil(pts[:, 0].max()))
    y1 = int(np.ceil(pts[:, 1].max()))
    return x0, y0, x1, y1


@lru_cache(maxsize=4)
def _load_paddle(lang: str, use_gpu: bool, det_model: str | None, rec_model: str | None):
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except ImportError as e:
        raise ImportError(
            "paddleocr is required. Install via `pip install paddleocr paddlepaddle`."
        ) from e
    # paddleocr 2.x accepts use_gpu/show_log; 3.x removed them. Build kwargs and
    # retry on TypeError, dropping unsupported keys one by one.
    kwargs: dict[str, Any] = {"lang": lang, "use_gpu": use_gpu, "show_log": False}
    if det_model:
        kwargs["det_model_dir"] = det_model
    if rec_model:
        kwargs["rec_model_dir"] = rec_model
    extra = {"use_angle_cls": True}
    for _ in range(8):
        try:
            return PaddleOCR(**extra, **kwargs)
        except Exception as e:  # PaddleOCR 3.x raises ValueError for unknown args
            msg = str(e)
            dropped = False
            for k in ("use_gpu", "show_log", "use_angle_cls", "det_model_dir", "rec_model_dir"):
                if k in msg and (k in kwargs or k in extra):
                    kwargs.pop(k, None)
                    extra.pop(k, None)
                    dropped = True
                    break
            if not dropped:
                raise
    return PaddleOCR(lang=lang)


class PaddleOCREngine(OCREngine):
    """PaddleOCR detection+recognition wrapper producing word-level boxes."""

    name = "paddleocr"

    def __init__(
        self,
        lang: str = "en",
        use_gpu: bool = False,
        det_model_dir: str | None = None,
        rec_model_dir: str | None = None,
    ) -> None:
        self.lang = lang
        self.use_gpu = use_gpu
        self.det_model_dir = det_model_dir
        self.rec_model_dir = rec_model_dir

    @property
    def _ocr(self):
        return _load_paddle(self.lang, self.use_gpu, self.det_model_dir, self.rec_model_dir)

    def read(self, image: np.ndarray) -> OCRResult:
        if image is None or image.size == 0:
            return OCRResult(words=[], image_size=(0, 0))
        h, w = image.shape[:2]
        raw = self._ocr.ocr(image, cls=True)
        # PaddleOCR returns either [page] or [[page]] depending on version — flatten.
        if not raw:
            return OCRResult(words=[], image_size=(w, h))
        page = raw[0] if raw and isinstance(raw[0], list) and raw[0] and isinstance(raw[0][0], list) else raw
        words: list[OCRWord] = []
        for item in page or []:
            if not item or len(item) < 2:
                continue
            poly, rec = item[0], item[1]
            try:
                text, conf = rec[0], float(rec[1])
            except (TypeError, IndexError, ValueError):
                continue
            text = (text or "").strip()
            if not text:
                continue
            try:
                bbox = _poly_to_bbox(poly)
            except Exception as e:  # pragma: no cover
                log.debug("bad polygon from paddle: %s", e)
                continue
            # Split multi-word strings — LayoutLMv3 tokenizer works better on word-level boxes.
            parts = text.split()
            if len(parts) == 1:
                words.append(OCRWord(text=text, bbox=bbox, confidence=conf))
            else:
                x0, y0, x1, y1 = bbox
                width = max(1, x1 - x0)
                total_chars = sum(len(p) for p in parts) or 1
                cursor = x0
                for p in parts:
                    span = int(width * (len(p) / total_chars))
                    wx1 = min(x1, cursor + span)
                    words.append(OCRWord(text=p, bbox=(cursor, y0, wx1, y1), confidence=conf))
                    cursor = wx1
        return OCRResult(words=words, image_size=(w, h))
