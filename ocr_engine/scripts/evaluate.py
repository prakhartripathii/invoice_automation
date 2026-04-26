"""Evaluate a trained model on a held-out labeled dataset."""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

import click

from ocr_engine.extraction.infer import InvoicePredictor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _gold_fields_from_json(jp: Path) -> dict[str, str]:
    data = json.loads(jp.read_text(encoding="utf-8"))
    words: list[str] = data["words"]
    labels: list[str] = data["labels"]
    out: dict[str, list[str]] = defaultdict(list)
    current: str | None = None
    for w, lbl in zip(words, labels):
        if lbl == "O":
            current = None
            continue
        tag, _, name = lbl.partition("-")
        name = name.lower()
        if tag == "B" or name != current:
            current = name
            if name not in out:
                out[name] = [w]
        else:
            out[name].append(w)
    return {k: " ".join(v) for k, v in out.items()}


@click.command()
@click.option("--model", type=click.Path(exists=True, file_okay=False), required=True)
@click.option("--data", type=click.Path(exists=True, file_okay=False), required=True)
def main(model: str, data: str) -> None:
    pred = InvoicePredictor(model)
    root = Path(data)
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    total = 0
    for jp in sorted(root.rglob("*.json")):
        try:
            gold = _gold_fields_from_json(jp)
        except Exception:
            continue
        ex = json.loads(jp.read_text(encoding="utf-8"))
        img = jp.parent / ex["image"]
        if not img.exists():
            continue
        got = pred.predict(str(img)).fields
        for k in set(gold) | set(got):
            g, p = gold.get(k, ""), got.get(k, "")
            if g and p and g.strip().lower() == p.strip().lower():
                tp[k] += 1
            elif p and not g:
                fp[k] += 1
            elif g and not p:
                fn[k] += 1
            else:
                fp[k] += 1
                fn[k] += 1
        total += 1
    click.echo(f"\nEvaluated {total} invoices")
    click.echo(f"{'field':<30} {'P':>6} {'R':>6} {'F1':>6}")
    for k in sorted(set(tp) | set(fp) | set(fn)):
        p = tp[k] / max(1, tp[k] + fp[k])
        r = tp[k] / max(1, tp[k] + fn[k])
        f1 = 2 * p * r / max(1e-9, p + r)
        click.echo(f"{k:<30} {p:>6.3f} {r:>6.3f} {f1:>6.3f}")


if __name__ == "__main__":
    main()
