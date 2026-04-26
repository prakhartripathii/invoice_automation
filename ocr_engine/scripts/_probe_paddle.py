"""Probe PaddleOCR 3.x API to inspect result shape. Throwaway."""
from paddleocr import PaddleOCR
import numpy as np
from PIL import Image
import io
import fitz

# Render page 1 of one PDF
doc = fitz.open(r"C:\Users\Prakhar Tripathi\Documents\invoice_mgnt\Invoice-Automation-Backend\ocr_engine\datasets\custom_invoices_raw\Invoice No. 202.pdf")
pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(250/72, 250/72), alpha=False)
img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
arr = np.array(img)

ocr = PaddleOCR(lang="en")
res = ocr.predict(arr)
print("type(res):", type(res))
print("len:", len(res) if hasattr(res, '__len__') else 'N/A')
print("type(res[0]):", type(res[0]))
r = res[0]
# Try common attributes/keys
for attr in ('rec_texts', 'rec_polys', 'rec_scores', 'json', 'res'):
    if hasattr(r, attr):
        v = getattr(r, attr)
        print(f"  has attr {attr}: type={type(v)}, sample={str(v)[:200]}")
if hasattr(r, '__getitem__'):
    try:
        print("  r['rec_texts'] sample:", str(r['rec_texts'])[:200])
    except Exception as e:
        print("  r[] err:", e)
print("dir(r) sample:", [a for a in dir(r) if not a.startswith('_')][:30])
