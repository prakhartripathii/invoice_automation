"""Central configuration — paths, training hyperparameters, OCR options.

Reads overrides from environment variables prefixed with `OCR_`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _env(key: str, default: str) -> str:
    return os.environ.get(f"OCR_{key}", default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(f"OCR_{key}", default))
    except (TypeError, ValueError):
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(f"OCR_{key}", default))
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(f"OCR_{key}")
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    # Paths
    project_root: Path = field(default_factory=_root)
    datasets_dir: Path = field(default_factory=lambda: _root() / "datasets")
    artifacts_dir: Path = field(default_factory=lambda: _root() / "artifacts")
    cache_dir: Path = field(default_factory=lambda: _root() / ".cache")

    # Model
    base_model_name: str = field(default_factory=lambda: _env("BASE_MODEL", "microsoft/layoutlmv3-base"))
    max_seq_length: int = field(default_factory=lambda: _env_int("MAX_SEQ_LEN", 512))

    # Training
    epochs: int = field(default_factory=lambda: _env_int("EPOCHS", 10))
    batch_size: int = field(default_factory=lambda: _env_int("BATCH_SIZE", 4))
    learning_rate: float = field(default_factory=lambda: _env_float("LR", 5e-5))
    weight_decay: float = field(default_factory=lambda: _env_float("WD", 0.01))
    warmup_ratio: float = field(default_factory=lambda: _env_float("WARMUP", 0.1))
    eval_split: float = field(default_factory=lambda: _env_float("EVAL_SPLIT", 0.1))
    seed: int = field(default_factory=lambda: _env_int("SEED", 42))

    # PaddleOCR
    paddle_lang: str = field(default_factory=lambda: _env("PADDLE_LANG", "en"))
    paddle_use_gpu: bool = field(default_factory=lambda: _env_bool("PADDLE_GPU", False))

    # Active learning
    uncertainty_strategy: str = field(default_factory=lambda: _env("UNCERTAINTY", "entropy"))
    active_batch_size: int = field(default_factory=lambda: _env_int("ACTIVE_BATCH", 200))

    def ensure_dirs(self) -> None:
        for p in (self.datasets_dir, self.artifacts_dir, self.cache_dir):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
