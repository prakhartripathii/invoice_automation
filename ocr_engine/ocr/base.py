"""Abstract OCR interface — swap implementations behind a stable contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class OCRWord:
    """A single recognized word plus its axis-aligned bounding box (x0, y0, x1, y1) in pixels."""

    text: str
    bbox: tuple[int, int, int, int]
    confidence: float = 0.0

    @property
    def width(self) -> int:
        return max(0, self.bbox[2] - self.bbox[0])

    @property
    def height(self) -> int:
        return max(0, self.bbox[3] - self.bbox[1])


@dataclass
class OCRResult:
    words: list[OCRWord] = field(default_factory=list)
    image_size: tuple[int, int] = (0, 0)  # (width, height)

    @property
    def texts(self) -> list[str]:
        return [w.text for w in self.words]

    @property
    def bboxes(self) -> list[tuple[int, int, int, int]]:
        return [w.bbox for w in self.words]

    def normalized_bboxes(self, target: int = 1000) -> list[list[int]]:
        """Scale boxes to [0, target] — the format LayoutLMv3 expects."""
        w, h = self.image_size
        if w <= 0 or h <= 0:
            return [[0, 0, 0, 0] for _ in self.words]
        out: list[list[int]] = []
        for x0, y0, x1, y1 in self.bboxes:
            nx0 = max(0, min(target, int(x0 / w * target)))
            ny0 = max(0, min(target, int(y0 / h * target)))
            nx1 = max(0, min(target, int(x1 / w * target)))
            ny1 = max(0, min(target, int(y1 / h * target)))
            if nx1 < nx0:
                nx0, nx1 = nx1, nx0
            if ny1 < ny0:
                ny0, ny1 = ny1, ny0
            out.append([nx0, ny0, nx1, ny1])
        return out


class OCREngine(ABC):
    """Any OCR backend (Paddle, Tesseract, Azure, docTR) must implement this."""

    name: str = "abstract"

    @abstractmethod
    def read(self, image: np.ndarray) -> OCRResult:  # pragma: no cover
        ...

    def read_batch(self, images: Sequence[np.ndarray]) -> list[OCRResult]:
        return [self.read(img) for img in images]
