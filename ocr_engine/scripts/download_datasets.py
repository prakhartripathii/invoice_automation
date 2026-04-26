"""Convert an already-downloaded public dataset to our internal schema."""
from __future__ import annotations

import logging
import sys

import click

from ocr_engine.data import convert_cord, convert_funsd, convert_sroie

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@click.command()
@click.option("--dataset", type=click.Choice(["sroie", "funsd", "cord"]), required=True)
@click.option("--src", type=click.Path(exists=True, file_okay=False), required=True,
              help="Path to the downloaded dataset root folder.")
@click.option("--out", type=click.Path(file_okay=False), required=True,
              help="Output directory — will hold image+JSON pairs.")
def main(dataset: str, src: str, out: str) -> None:
    fn = {"sroie": convert_sroie, "funsd": convert_funsd, "cord": convert_cord}[dataset]
    n = fn(src, out)
    click.echo(f"Converted {n} examples from {dataset} → {out}")
    sys.exit(0 if n > 0 else 1)


if __name__ == "__main__":
    main()
