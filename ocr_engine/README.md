# OCR Engine — Invoice Field Extraction Pipeline

A standalone, self-contained module for building a high-accuracy invoice OCR engine.

**Architecture:** `PaddleOCR (detect + recognize) → LayoutLMv3 (field extraction) → Champ/Challenger ensemble → Active-learning loop`.

This folder is designed to be dropped into any Python project. It has zero coupling with the `backend/` folder — integrate via the public API in `ocr_engine.extraction.infer.InvoicePredictor`.

---

## Features

- **Preprocessing:** deskew, denoise, Sauvola binarize, auto-orient.
- **OCR base:** PaddleOCR (multilingual, DBNet+CRNN) wrapped behind an abstract `OCREngine` interface.
- **Field extraction:** fine-tuned LayoutLMv3 mapping tokens + bounding boxes → (vendor, invoice_number, date, total, etc.).
- **Ensemble:** Champ/Challenger decision engine — auto-approve only when both agree.
- **Training data ingestion:** SROIE, CORD, FUNSD public-dataset converters; SynthDoG-style synthetic generator; Label Studio import/export.
- **Active learning:** uncertainty sampling (entropy, margin) + feedback loop ingesting human corrections from the review queue.

## Folder layout

```
ocr_engine/
├── config/           # label schema, settings, paths
├── data/             # dataset loaders, converters, synthetic generator
├── preprocessing/    # image cleanup
├── ocr/              # PaddleOCR wrapper
├── extraction/       # LayoutLMv3 training + inference
├── ensemble/         # Champ/Challenger agreement engine
├── active_learning/  # uncertainty + feedback ingestion
├── scripts/          # CLI entry points
├── tests/            # pytest unit tests
└── docs/             # setup guide
```

## Quick start

```bash
cd ocr_engine
python -m venv .venv
.venv\Scripts\activate           # Windows
pip install -r requirements.txt
pip install -e .

# 1. Download public datasets
python -m ocr_engine.scripts.download_datasets --dataset sroie --out ./datasets

# 2. Generate synthetic invoices
python -m ocr_engine.scripts.generate_synthetic --count 5000 --out ./datasets/synthetic

# 3. Fine-tune LayoutLMv3
python -m ocr_engine.scripts.train_layoutlm --data ./datasets --epochs 10

# 4. Evaluate
python -m ocr_engine.scripts.evaluate --model ./artifacts/layoutlmv3-invoice --data ./datasets/eval

# 5. Inference
python -c "from ocr_engine.extraction.infer import InvoicePredictor; \
           p = InvoicePredictor('./artifacts/layoutlmv3-invoice'); \
           print(p.predict('sample_invoice.pdf'))"
```

## Integration with backend

In the backend, replace the existing OCR call with:

```python
from ocr_engine.extraction.infer import InvoicePredictor
from ocr_engine.ensemble.champ_challenger import ChampChallenger

champ = InvoicePredictor('./artifacts/layoutlmv3-champ')
challenger = InvoicePredictor('./artifacts/layoutlmv3-challenger')
ensemble = ChampChallenger(champ, challenger)

result = ensemble.predict(image_path)
# result.fields, result.decision, result.confidence, result.agreement_ratio
```

## Active-learning loop

Every invoice the ops team corrects in the review queue should be posted back to:

```python
from ocr_engine.active_learning.feedback_loop import FeedbackIngestor
FeedbackIngestor('./datasets/active').ingest(invoice_id, corrected_fields, image_path)
```

Retrain nightly / weekly with `scripts/train_layoutlm.py --data ./datasets` — the active-learning samples are merged automatically.

## Milestones

| Cycle | Data | Expected field-F1 |
|------|------|-------------------|
| 0    | Off-the-shelf PaddleOCR + rules | 0.82 |
| 1    | +SROIE+CORD+5k synthetic         | 0.90 |
| 2    | +5k human-labeled                | 0.94 |
| 3+   | +active-learning (10k+)          | 0.97+ |

See `docs/SETUP.md` for the full training guide.
