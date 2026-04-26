"""Ingest one human-corrected invoice into the active-learning dataset.

Usage (from backend code):
    python -m ocr_engine.scripts.ingest_review_feedback \
        --id abc123 --image /path/to/invoice.png \
        --fields '{"vendor_name":"Acme","total_amount":"123.45"}'
"""
from __future__ import annotations

import json
import logging

import click

from ocr_engine.active_learning.feedback_loop import FeedbackIngestor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@click.command()
@click.option("--id", "sample_id", required=True)
@click.option("--image", "image_path", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--fields", "fields_json", required=True, help="JSON object of field_name -> value")
@click.option("--out", type=click.Path(file_okay=False), default="./datasets/active")
def main(sample_id: str, image_path: str, fields_json: str, out: str) -> None:
    fields = json.loads(fields_json)
    if not isinstance(fields, dict):
        raise click.BadParameter("--fields must be a JSON object")
    ing = FeedbackIngestor(out)
    saved = ing.ingest(sample_id, fields, image_path)
    click.echo(f"Saved: {saved}")


if __name__ == "__main__":
    main()
