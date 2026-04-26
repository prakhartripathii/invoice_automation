"""End-to-end invoice field extraction: image -> PaddleOCR -> LayoutLMv3 -> fields dict."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..config import ID2LABEL
from ..ocr.base import OCREngine, OCRResult
from ..ocr.paddle_engine import PaddleOCREngine
from ..preprocessing import preprocess_for_ocr
from .layoutlmv3_model import load_model, load_processor

log = logging.getLogger(__name__)


@dataclass
class Prediction:
    fields: dict[str, str] = field(default_factory=dict)
    token_labels: list[str] = field(default_factory=list)
    token_words: list[str] = field(default_factory=list)
    token_confidences: list[float] = field(default_factory=list)
    mean_confidence: float = 0.0
    ocr_result: OCRResult | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "fields": self.fields,
            "mean_confidence": self.mean_confidence,
            "token_labels": self.token_labels,
            "token_words": self.token_words,
        }


class InvoicePredictor:
    """Production-ready predictor. Thread-safe after construction."""

    def __init__(
        self,
        model_path: str | Path,
        ocr_engine: OCREngine | None = None,
        *,
        device: str | None = None,
    ) -> None:
        try:
            import torch
        except ImportError as e:
            raise ImportError("torch is required for inference") from e
        self.model_path = str(model_path)
        self.processor = load_processor(self.model_path)
        self.model = load_model(self.model_path)
        self.model.eval()
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.ocr = ocr_engine or PaddleOCREngine()
        self._torch = torch

    def _run_ocr(self, image_src: Any) -> tuple[np.ndarray, OCRResult]:
        img = preprocess_for_ocr(image_src, do_deskew=True, do_denoise=True, do_binarize=False)
        ocr_res = self.ocr.read(img)
        return img, ocr_res

    def _infer_tokens(self, image: np.ndarray, ocr: OCRResult) -> Prediction:
        if not ocr.words:
            return Prediction(ocr_result=ocr)
        from PIL import Image

        pil = Image.fromarray(image[:, :, ::-1]) if image.ndim == 3 else Image.fromarray(image).convert("RGB")
        words = [w.text for w in ocr.words]
        boxes = ocr.normalized_bboxes(1000)
        enc = self.processor(
            pil,
            words,
            boxes=boxes,
            truncation=True,
            padding="max_length",
            max_length=512,
            return_tensors="pt",
            return_offsets_mapping=False,
        )
        enc = {k: v.to(self.device) for k, v in enc.items()}

        # transformers wraps forward(); co_varnames doesn't reflect the model's real signature.
        valid = {"input_ids", "attention_mask", "bbox", "pixel_values", "token_type_ids"}
        with self._torch.no_grad():
            out = self.model(**{k: v for k, v in enc.items() if k in valid})
        logits = out.logits[0]  # (seq, num_labels)
        probs = self._torch.softmax(logits, dim=-1)
        conf, pred = probs.max(dim=-1)
        pred_np = pred.cpu().numpy()
        conf_np = conf.cpu().numpy()

        # Map tokens back to word-level predictions using word_ids() from processor's tokenizer
        word_ids = enc_word_ids(self.processor, words, boxes, pil, self.device)
        word_labels: dict[int, str] = {}
        word_confs: dict[int, list[float]] = {}
        for tok_idx, wid in enumerate(word_ids):
            if wid is None or tok_idx >= len(pred_np):
                continue
            if wid in word_labels:
                # first subword already wrote the label; just collect confidence
                word_confs[wid].append(float(conf_np[tok_idx]))
                continue
            word_labels[wid] = ID2LABEL.get(int(pred_np[tok_idx]), "O")
            word_confs[wid] = [float(conf_np[tok_idx])]

        token_labels: list[str] = []
        token_confidences: list[float] = []
        for wi, _ in enumerate(words):
            token_labels.append(word_labels.get(wi, "O"))
            cs = word_confs.get(wi, [0.0])
            token_confidences.append(sum(cs) / len(cs))

        fields = _tokens_to_fields(words, token_labels)
        mean_conf = float(sum(token_confidences) / len(token_confidences)) if token_confidences else 0.0
        return Prediction(
            fields=fields,
            token_labels=token_labels,
            token_words=words,
            token_confidences=token_confidences,
            mean_confidence=mean_conf,
            ocr_result=ocr,
        )

    def predict(self, image_src: Any) -> Prediction:
        image, ocr = self._run_ocr(image_src)
        return self._infer_tokens(image, ocr)


def enc_word_ids(processor, words: list[str], boxes: list[list[int]], image, device: str) -> list[int | None]:
    """Re-tokenize just to access word_ids — processor.encoding.word_ids() isn't always exposed."""
    enc = processor(
        image,
        words,
        boxes=boxes,
        truncation=True,
        padding="max_length",
        max_length=512,
        return_tensors="pt",
    )
    # LayoutLMv3Processor wraps a fast tokenizer; encoding[0] carries word_ids().
    try:
        return enc.word_ids(batch_index=0)  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover
        # Fallback: assume every non-special token is its own word — lossy but safe.
        return [i if i < len(words) else None for i in range(enc["input_ids"].shape[-1])]


def _tokens_to_fields(words: list[str], labels: list[str]) -> dict[str, str]:
    """Stitch B-/I- tagged token spans into a single string per field. Takes the first span per field."""
    fields: dict[str, list[str]] = {}
    current_field: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_field, buffer
        if current_field and buffer and current_field not in fields:
            fields[current_field] = [" ".join(buffer).strip()]
        current_field = None
        buffer = []

    for w, lbl in zip(words, labels):
        if lbl == "O":
            flush()
            continue
        tag, _, name = lbl.partition("-")
        name = name.lower()
        if tag == "B":
            flush()
            current_field = name
            buffer = [w]
        elif tag == "I" and current_field == name:
            buffer.append(w)
        else:
            flush()
            current_field = name
            buffer = [w]
    flush()
    return {k: v[0] for k, v in fields.items()}
