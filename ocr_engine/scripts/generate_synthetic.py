"""Generate N synthetic labeled invoices."""
from __future__ import annotations

import logging

import click

from ocr_engine.data.synthetic import SyntheticInvoiceGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@click.command()
@click.option("--count", type=int, default=1000, show_default=True)
@click.option("--out", type=click.Path(file_okay=False), required=True)
@click.option("--seed", type=int, default=None)
def main(count: int, out: str, seed: int | None) -> None:
    gen = SyntheticInvoiceGenerator(seed=seed)
    n = gen.generate_batch(count, out)
    click.echo(f"Generated {n} invoices in {out}")


if __name__ == "__main__":
    main()
