"""Export internal-schema invoices to a Label Studio tasks JSON."""
from __future__ import annotations

import logging

import click

from ocr_engine.data.label_studio import export_to_label_studio

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@click.command()
@click.option("--src", type=click.Path(exists=True, file_okay=False), required=True)
@click.option("--out", type=click.Path(dir_okay=False), required=True)
@click.option("--url-prefix", default="/data/local-files/?d=")
def main(src: str, out: str, url_prefix: str) -> None:
    n = export_to_label_studio(src, out, image_url_prefix=url_prefix)
    click.echo(f"Wrote {n} tasks to {out}")


if __name__ == "__main__":
    main()
