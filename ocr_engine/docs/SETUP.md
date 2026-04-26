# Setup & Training Guide

## 1. Environment

```powershell
cd ocr_engine
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

**Windows extras:**
- Install **Poppler** (needed by `pdf2image`): https://github.com/oschwartz10612/poppler-windows — add its `bin/` to PATH.
- Optional: install **Tesseract** for auto-orientation (`pytesseract` OSD).

**GPU:**
- For training, install CUDA-enabled PyTorch: `pip install torch --index-url https://download.pytorch.org/whl/cu121`.
- For PaddleOCR GPU: `pip install paddlepaddle-gpu` and set `OCR_PADDLE_GPU=true`.

## 2. Data pipeline (bottleneck)

### a. Public datasets (free starter — ~2k labeled invoices)
Download manually and convert:

```powershell
python -m ocr_engine.scripts.download_datasets --dataset sroie --src C:\data\sroie --out .\datasets\sroie
python -m ocr_engine.scripts.download_datasets --dataset cord  --src C:\data\cord  --out .\datasets\cord
python -m ocr_engine.scripts.download_datasets --dataset funsd --src C:\data\funsd --out .\datasets\funsd
```

Links:
- **SROIE** — https://rrc.cvc.uab.es/?ch=13
- **CORD** — https://github.com/clovaai/cord
- **FUNSD** — https://guillaumejaume.github.io/FUNSD/

### b. Synthetic (free — unlimited)

```powershell
python -m ocr_engine.scripts.generate_synthetic --count 10000 --out .\datasets\synthetic --seed 42
```

Produces vector-perfect PDFs → rasterized PNGs with exact word boxes and ground-truth labels. Great for bootstrapping.

### c. Human labeling (expensive but highest value)

1. Export unlabeled OCR'd invoices to Label Studio:
   ```powershell
   python -m ocr_engine.scripts.export_for_labelstudio --src .\datasets\raw --out .\ls_tasks.json
   ```
2. Boot Label Studio (`pip install label-studio && label-studio start`).
3. Create a project with **RectangleLabels** config — one label per field in `config/labels.py::FIELD_LABELS`.
4. Import `ls_tasks.json` and have your ops team draw boxes on 2–5k real invoices.
5. Export the project and import back:
   ```python
   from ocr_engine.data.label_studio import import_from_label_studio
   import_from_label_studio("./export.json", "./images", "./datasets/human")
   ```

### d. Active-learning loop (compounding value)

Every time the ops team approves/corrects an invoice in the DocuSense review queue, wire the backend to call:

```python
from ocr_engine.active_learning.feedback_loop import FeedbackIngestor
FeedbackIngestor("./datasets/active").ingest(
    sample_id=str(invoice.id),
    field_values={"vendor_name": invoice.vendor_name, "total_amount": str(invoice.total_amount), ...},
    image_path=invoice.source_image_path,
)
```

After ~1000 new samples, retrain. Repeat.

## 3. Training

```powershell
python -m ocr_engine.scripts.train_layoutlm --data .\datasets --epochs 10 --batch-size 4
```

Artifacts go to `./artifacts/layoutlmv3-invoice/`. The best model (highest F1 on eval split) is kept automatically.

**Champ + Challenger:** train twice with different seeds / data subsets:

```powershell
python -m ocr_engine.scripts.train_layoutlm --data .\datasets --seed 1 --out .\artifacts\champ
python -m ocr_engine.scripts.train_layoutlm --data .\datasets --seed 99 --out .\artifacts\challenger
```

## 4. Evaluation

```powershell
python -m ocr_engine.scripts.evaluate --model .\artifacts\champ --data .\datasets\heldout
```

## 5. Backend integration

```python
from ocr_engine.extraction.infer import InvoicePredictor
from ocr_engine.ensemble.champ_challenger import ChampChallenger

champ = InvoicePredictor("./artifacts/champ")
challenger = InvoicePredictor("./artifacts/challenger")
ensemble = ChampChallenger(champ, challenger, auto_approve_threshold=0.9, min_confidence=0.75)

decision = ensemble.predict("/path/to/invoice.png")
# decision.decision -> AUTO_APPROVE | REVIEW_REQUIRED | REJECT
# decision.fields, .agreement_ratio, .weighted_confidence, .mismatches, .reasons
```

## 6. Retraining schedule

| Trigger | What to run |
|---------|-------------|
| Nightly | `train_layoutlm.py` on current active/ dataset if ≥200 new samples |
| Weekly  | Full retrain on all data (synthetic + public + human + active) |
| Monthly | Re-evaluate on held-out set; promote challenger → champ if F1 is better |

## 7. Tests

```powershell
pytest -q
```

Should report ~20 tests passing with no heavy dependencies (torch/paddle tests are skipped if the libs aren't installed).
