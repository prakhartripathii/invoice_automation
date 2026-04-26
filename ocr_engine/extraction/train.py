"""Fine-tune LayoutLMv3 for token-classification on labeled invoices."""
from __future__ import annotations

import logging
from pathlib import Path

from ..config import get_settings
from .dataset import InvoiceLayoutDataset, split_dataset
from .layoutlmv3_model import load_model, load_processor, save_artifacts
from .metrics import compute_token_metrics

log = logging.getLogger(__name__)


def train(
    data_dir: str | Path,
    output_dir: str | Path | None = None,
    *,
    epochs: int | None = None,
    batch_size: int | None = None,
    learning_rate: float | None = None,
    eval_split: float | None = None,
    seed: int | None = None,
    base_model: str | None = None,
) -> Path:
    """Fine-tune LayoutLMv3. Returns path to saved artifacts."""
    try:
        from transformers import Trainer, TrainingArguments  # type: ignore
    except ImportError as e:
        raise ImportError("transformers is required. `pip install transformers accelerate`") from e

    s = get_settings()
    output_dir = Path(output_dir or (s.artifacts_dir / "layoutlmv3-invoice"))
    output_dir.mkdir(parents=True, exist_ok=True)

    processor = load_processor(base_model)
    model = load_model(base_model)
    dataset = InvoiceLayoutDataset.from_directory(data_dir, processor, max_length=s.max_seq_length)
    train_ds, eval_ds = split_dataset(dataset, eval_ratio=eval_split or s.eval_split, seed=seed or s.seed)
    log.info("Train=%d  Eval=%d", len(train_ds), len(eval_ds))

    args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=epochs or s.epochs,
        per_device_train_batch_size=batch_size or s.batch_size,
        per_device_eval_batch_size=batch_size or s.batch_size,
        learning_rate=learning_rate or s.learning_rate,
        weight_decay=s.weight_decay,
        warmup_ratio=s.warmup_ratio,
        eval_strategy="epoch" if len(eval_ds) else "no",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=bool(len(eval_ds)),
        metric_for_best_model="f1" if len(eval_ds) else None,
        greater_is_better=True,
        logging_steps=20,
        seed=seed or s.seed,
        report_to=[],  # silence integrations by default
        remove_unused_columns=False,
    )

    # transformers 5.x uses `processing_class`; 4.x uses `tokenizer`. Try new name first.
    trainer_kwargs = dict(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=eval_ds if len(eval_ds) else None,
        compute_metrics=compute_token_metrics if len(eval_ds) else None,
    )
    try:
        trainer = Trainer(processing_class=processor, **trainer_kwargs)
    except TypeError:
        trainer = Trainer(tokenizer=processor, **trainer_kwargs)
    trainer.train()
    save_artifacts(trainer.model, processor, output_dir)
    if len(eval_ds):
        final = trainer.evaluate()
        log.info("Final eval: %s", final)
    return output_dir
