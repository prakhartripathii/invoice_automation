"""Agent 1 — Image preprocessing.

Handles deskewing, denoising, and contrast enhancement. 
Includes high-accuracy binarization for better OCR results.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np

from app.agents.base import BaseAgent
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class PreprocessingInput:
    file_bytes: bytes
    mime_type: str


@dataclass
class PreprocessingOutput:
    images: List[np.ndarray]       # cleaned BGR images
    encoded_pngs: List[bytes]      # serialized for sending to cloud OCR
    page_count: int


class PreprocessingAgent(BaseAgent[PreprocessingInput, PreprocessingOutput]):
    name = "preprocessing"

    def _run(self, inputs: PreprocessingInput) -> PreprocessingOutput:
        images = self._decode(inputs.file_bytes, inputs.mime_type)
        cleaned: List[np.ndarray] = []
        encoded: List[bytes] = []
        
        for img in images:
            # The core cleaning step
            processed = self._enhance(img)
            cleaned.append(processed)
            
            # Re-encoding for the cloud OCR engines (Azure/Paddle)
            ok, buf = cv2.imencode(".png", processed)
            if ok:
                encoded.append(buf.tobytes())
                
        return PreprocessingOutput(
            images=cleaned,
            encoded_pngs=encoded,
            page_count=len(cleaned),
        )

    # ---------- Decoding ----------
    def _decode(self, data: bytes, mime: str) -> List[np.ndarray]:
        mime = (mime or "").lower()
        if "pdf" in mime or data[:4] == b"%PDF":
            return self._decode_pdf(data)
        return self._decode_image(data)

    def _decode_image(self, data: bytes) -> List[np.ndarray]:
        arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Unable to decode image bytes")
        return [img]

    def _decode_pdf(self, data: bytes) -> List[np.ndarray]:
        try:
            from pdf2image import convert_from_bytes
            # Using 300 DPI for higher extraction accuracy
            pages = convert_from_bytes(data, dpi=300, fmt="png")
            return [
                cv2.cvtColor(np.array(p), cv2.COLOR_RGB2BGR) for p in pages
            ]
        except Exception as exc:
            log.warning("pdf2image_unavailable", error=str(exc))
            return []

    # ---------- Enhancement & Cleaning ----------
    @staticmethod
    def _enhance(img: np.ndarray) -> np.ndarray:
        # 1. Convert to Gray
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2. Resizing (If image is too small, OCR accuracy drops)
        height, width = gray.shape
        if width < 1500:
            scale = 1500 / width
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        # 3. Denoise (Removes paper grain)
        denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)

        # 4. Deskew (Straightens the page)
        angle = PreprocessingAgent._detect_skew(denoised)
        rotated = PreprocessingAgent._rotate(denoised, angle) if abs(angle) > 0.5 else denoised

        # 5. Contrast Enhancement (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(rotated)

        # 6. UPDATED: Binarization / Thresholding
        # This turns the image into pure black and white, removing all background shadows
        cleaned = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )

        # Convert back to BGR to match original expected output format
        return cv2.cvtColor(cleaned, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def _detect_skew(gray: np.ndarray) -> float:
        try:
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(
                edges, 1, np.pi / 180, 200, minLineLength=100, maxLineGap=10
            )
            if lines is None:
                return 0.0
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if x2 == x1: continue
                a = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                if -45 < a < 45:
                    angles.append(a)
            return float(np.median(angles)) if angles else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _rotate(img: np.ndarray, angle: float) -> np.ndarray:
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(
            img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )