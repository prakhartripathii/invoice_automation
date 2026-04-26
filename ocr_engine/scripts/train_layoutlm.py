"""Fine-tune LayoutLMv3 for invoice field extraction."""
from __future__ import annotations

import logging

import click

from ocr_engine.extraction.train import train

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@click.command()
@click.option("--data", type=click.Path(exists=True, file_okay=False), required=True,
              help="Root dir containing JSON+image pairs (recursively).")
@click.option("--out", type=click.Path(file_okay=False), default=None,
              help="Output dir for model artifacts. Default: artifacts/layoutlmv3-invoice")
@click.option("--epochs", type=int, default=None)
@click.option("--batch-size", type=int, default=None)
@click.option("--lr", type=float, default=None)
@click.option("--base-model", type=str, default=None)
@click.option("--seed", type=int, default=None)
def main(data: str, out: str | None, epochs: int | None, batch_size: int | None,
         lr: float | None, base_model: str | None, seed: int | None) -> None:
    saved = train(
        data_dir=data,
        output_dir=out,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=lr,
        base_model=base_model,
        seed=seed,
    )
    click.echo(f"Saved to: {saved}")


if __name__ == "__main__":
    main()
