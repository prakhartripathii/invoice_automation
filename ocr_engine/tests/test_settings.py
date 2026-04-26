import os

from ocr_engine.config.settings import Settings, get_settings


def test_defaults():
    s = Settings()
    assert s.base_model_name.startswith("microsoft/layoutlmv3")
    assert s.epochs > 0
    assert s.batch_size > 0
    assert 0 < s.learning_rate < 1


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("OCR_EPOCHS", "7")
    monkeypatch.setenv("OCR_BATCH_SIZE", "2")
    monkeypatch.setenv("OCR_LR", "0.001")
    monkeypatch.setenv("OCR_PADDLE_GPU", "true")
    s = Settings()
    assert s.epochs == 7
    assert s.batch_size == 2
    assert s.learning_rate == 0.001
    assert s.paddle_use_gpu is True


def test_get_settings_cached():
    a = get_settings()
    b = get_settings()
    assert a is b
