"""Invoice field label schema (BIO tagging for token-level LayoutLMv3 training)."""
from __future__ import annotations

# Business fields to extract. Order matters for display but not for training.
FIELD_LABELS: list[str] = [
    "vendor_name",
    "vendor_address",
    "vendor_phone",
    "vendor_email",
    "vendor_tax_id",
    "invoice_number",
    "invoice_date",
    "due_date",
    "purchase_order",
    "currency",
    "subtotal",
    "tax_amount",
    "gst",
    "igst",
    "cgst",
    "total_quantity",
    "total_amount",
    "terms_and_conditions",
    "line_item_description",
    "line_item_quantity",
    "line_item_unit_price",
    "line_item_amount",
]


def _build_bio_labels(fields: list[str]) -> list[str]:
    labels = ["O"]
    for f in fields:
        labels.append(f"B-{f.upper()}")
        labels.append(f"I-{f.upper()}")
    return labels


BIO_LABELS: list[str] = _build_bio_labels(FIELD_LABELS)
LABEL2ID: dict[str, int] = {lbl: i for i, lbl in enumerate(BIO_LABELS)}
ID2LABEL: dict[int, str] = {i: lbl for lbl, i in LABEL2ID.items()}
NUM_LABELS: int = len(BIO_LABELS)
