"""Assemble the Strategy-B fine-tuning dataset.

Strategy B = mix newly-labeled invoices with a sample of the existing dataset
so the fine-tune doesn't catastrophically forget the original 15 fields when
learning the 7 new ones (vendor_phone, vendor_email, gst, igst, cgst,
total_quantity, terms_and_conditions).

This script just shuffles and copies existing JSON+JPG pairs into one folder.

Run AFTER you've labeled custom_invoices/ (replaced "O" placeholders with
real B-/I- tags) and AFTER the current 25h training has finished.

Usage:
    python -m ocr_engine.scripts.build_finetune_mix \
        --new ocr_engine/datasets/custom_invoices \
        --pool ocr_engine/datasets/sroie_train ocr_engine/datasets/funsd \
        --out ocr_engine/datasets/finetune_mix \
        --sample 150
"""
from __future__ import annotations

import logging
import random
import shutil
from pathlib import Path

import click

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _collect_pairs(folder: Path) -> list[tuple[Path, Path]]:
    """Return list of (json, image) pairs found under folder."""
    pairs: list[tuple[Path, Path]] = []
    for jf in sorted(folder.rglob("*.json")):
        # Find sibling image (jpg/png).
        for ext in (".jpg", ".jpeg", ".png"):
            img = jf.with_suffix(ext)
            if img.exists():
                pairs.append((jf, img))
                break
    return pairs


def _copy_pair(jf: Path, img: Path, dst: Path, prefix: str) -> None:
    new_jf = dst / f"{prefix}_{jf.name}"
    new_img = dst / f"{prefix}_{img.name}"
    shutil.copy2(img, new_img)
    # Patch the "image" field inside the JSON so it points at the renamed image.
    import json
    data = json.loads(jf.read_text(encoding="utf-8"))
    data["image"] = new_img.name
    new_jf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@click.command()
@click.option("--new", "new_dir", type=click.Path(exists=True, file_okay=False),
              required=True, help="Folder of newly-labeled invoices")
@click.option("--pool", "pool_dirs", type=click.Path(exists=True, file_okay=False),
              multiple=True, required=True,
              help="One or more existing-dataset folders to sample from")
@click.option("--out", "out_dir", type=click.Path(file_okay=False),
              required=True, help="Output mix folder (will be created/cleared)")
@click.option("--sample", type=int, default=150, show_default=True,
              help="How many existing examples to sample (Strategy B uses ~150)")
@click.option("--seed", type=int, default=42, show_default=True)
def main(new_dir: str, pool_dirs: tuple[str, ...], out_dir: str, sample: int, seed: int) -> None:
    rng = random.Random(seed)
    dst = Path(out_dir)
    if dst.exists():
        log.info("Clearing existing %s", dst)
        shutil.rmtree(dst)
    dst.mkdir(parents=True)

    # 1. Copy ALL new examples (they're scarce, we want every one)
    new_pairs = _collect_pairs(Path(new_dir))
    log.info("Copying %d new labeled examples", len(new_pairs))
    for jf, img in new_pairs:
        _copy_pair(jf, img, dst, prefix="new")

    # 2. Sample from the pool dirs
    pool: list[tuple[Path, Path]] = []
    for p in pool_dirs:
        pool.extend(_collect_pairs(Path(p)))
    log.info("Pool size across %d folders: %d examples", len(pool_dirs), len(pool))
    if not pool:
        raise SystemExit("No pool examples found.")
    k = min(sample, len(pool))
    chosen = rng.sample(pool, k)
    log.info("Sampling %d existing examples", k)
    for jf, img in chosen:
        _copy_pair(jf, img, dst, prefix="pool")

    total = len(_collect_pairs(dst))
    log.info("Done. Mix dir contains %d pairs at %s", total, dst)


if __name__ == "__main__":
    main()
