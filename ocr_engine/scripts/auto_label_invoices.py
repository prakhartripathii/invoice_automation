"""Heuristic auto-labeler for the Vizlogic invoice dataset.

Reads each *.json in --in (output of prepare_custom_pdfs.py) and replaces the
placeholder "O" labels with BIO tags using a mix of regex + keyword anchors.

Designed for the Vizlogic Digital Solutions invoice template; works on both
page 1 (header + line items) and page 2 (totals + email/phone/bank).

Usage:
    python -m ocr_engine.scripts.auto_label_invoices \
        --in ocr_engine/datasets/custom_invoices --inplace

After running, you should spot-check 3-5 JSONs (open the JPG side-by-side)
and correct any mislabels by hand. Then run build_finetune_mix.py.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import click

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---- regex patterns ----
RE_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
RE_EMAIL_PARTIAL = re.compile(r"^[\w.+-]+@")           # the right half after a split
RE_EMAIL_PREFIX = re.compile(r"^[\w.+-]+\.$")          # the left half ("pradeep.")
RE_PHONE = re.compile(r"^(\+\d{10,13}|[6-9]\d{9})$")  # +91xxx or 10-digit Indian mobile
RE_DATE = re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{2,4}[,]?$")
RE_GSTIN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")
RE_AMOUNT = re.compile(r"^\d{1,3}(?:,\d{3})*(?:\.\d+)?$")     # 1,180.00 or 90.00 or 1000
RE_INVOICE_NUM = re.compile(r"^[A-Z]{2,}/[A-Z0-9/\-]+$")      # VZ/GGN/25-26/198
RE_PO_NUM = re.compile(r"^[A-Z]{2,}/[A-Z0-9/\-]+[,]?$")       # SC/25-26/PO/03244,


def _set_span(labels: list[str], start: int, end: int, field: str) -> int:
    """Set BIO labels for words[start:end] to field, return number written."""
    n = 0
    for i in range(start, min(end, len(labels))):
        labels[i] = (f"B-{field.upper()}" if i == start else f"I-{field.upper()}")
        n += 1
    return n


def _find_seq(words: list[str], seq: list[str], start: int = 0) -> int:
    """Return index where seq matches words, or -1."""
    L = len(seq)
    for i in range(start, len(words) - L + 1):
        if all(words[i + j].lower().rstrip(":,.") == seq[j].lower().rstrip(":,.") for j in range(L)):
            return i
    return -1


def label_words(words: list[str]) -> list[str]:
    n = len(words)
    labels = ["O"] * n

    # ---- 1) Vendor name: tokens after "Tax Invoice" up to address start ----
    # Pattern: "Tax", "Invoice", "Vizlogic", "Digital", "Solutions", "Pvt", "Ltd"
    idx = _find_seq(words, ["Tax", "Invoice"])
    if idx >= 0:
        start = idx + 2
        # vendor name runs until first address-like token (digits, "Plot", "MiQB", etc.)
        end = start
        while end < n and end - start < 8:
            w = words[end]
            if w in {"MiQB", "Plot", "GSTIN/UIN:", "GSTIN/UIN"} or RE_GSTIN.match(w):
                break
            if w[0].isdigit():
                break
            end += 1
        if end > start:
            _set_span(labels, start, end, "vendor_name")
            # ---- 2) Vendor address: until first GSTIN/UIN occurrence ----
            addr_start = end
            addr_end = addr_start
            while addr_end < n:
                w = words[addr_end]
                if w in {"GSTIN/UIN:", "GSTIN/UIN"} or RE_GSTIN.match(w):
                    break
                addr_end += 1
                if addr_end - addr_start > 20:  # safety cap
                    break
            if addr_end > addr_start:
                _set_span(labels, addr_start, addr_end, "vendor_address")

    # ---- 3) Vendor tax ID: first GSTIN-format token in the doc ----
    for i, w in enumerate(words):
        if RE_GSTIN.match(w):
            _set_span(labels, i, i + 1, "vendor_tax_id")
            break

    # ---- 4) Invoice number: token after "Invoice" + "No." ----
    i = _find_seq(words, ["Invoice", "No."])
    if i >= 0 and i + 2 < n:
        cand = words[i + 2]
        if RE_INVOICE_NUM.match(cand):
            _set_span(labels, i + 2, i + 3, "invoice_number")

    # ---- 5) Purchase order: tokens after "Buyer's" "Order" "No." ----
    i = _find_seq(words, ["Buyer's", "Order", "No."])
    if i >= 0:
        po_start = i + 3
        po_end = po_start
        while po_end < n and RE_PO_NUM.match(words[po_end]) and po_end - po_start < 8:
            po_end += 1
        if po_end > po_start:
            _set_span(labels, po_start, po_end, "purchase_order")

    # ---- 6) Invoice date: first token matching DD-MMM-YY anywhere ----
    for i, w in enumerate(words):
        if RE_DATE.match(w):
            # Only label the FIRST date occurrence as invoice_date
            _set_span(labels, i, i + 1, "invoice_date")
            break

    # ---- 7) CGST / IGST / GST (SGST) values: number following the @9%_OUTPUT tag ----
    for i, w in enumerate(words):
        wu = w.upper()
        if "CGST" in wu and "@" in w and i + 1 < n and RE_AMOUNT.match(words[i + 1]):
            if labels[i + 1] == "O":
                _set_span(labels, i + 1, i + 2, "cgst")
        elif "IGST" in wu and "@" in w and i + 1 < n and RE_AMOUNT.match(words[i + 1]):
            if labels[i + 1] == "O":
                _set_span(labels, i + 1, i + 2, "igst")
        elif "SGST" in wu and "@" in w and i + 1 < n and RE_AMOUNT.match(words[i + 1]):
            if labels[i + 1] == "O":
                _set_span(labels, i + 1, i + 2, "gst")  # SGST mapped to gst slot

    # ---- 8) Total amount: standalone "Total" followed by an amount.
    # Skip the column header "HSN/SAC Total" by requiring the next token to be a number.
    for i, w in enumerate(words):
        if w == "Total" and i + 1 < n and RE_AMOUNT.match(words[i + 1]):
            if labels[i + 1] == "O":
                _set_span(labels, i + 1, i + 2, "total_amount")
                break  # only the first such pair (grand total)

    # ---- 9) Vendor email (regex) ----
    # Handle split case FIRST so the second token's full-email regex doesn't overwrite.
    i = 0
    while i < n:
        w = words[i]
        if RE_EMAIL_PREFIX.match(w) and i + 1 < n and RE_EMAIL_PARTIAL.match(words[i + 1]):
            _set_span(labels, i, i + 2, "vendor_email")
            i += 2
            continue
        if RE_EMAIL.match(w) and labels[i] == "O":
            _set_span(labels, i, i + 1, "vendor_email")
        i += 1

    # ---- 10) Vendor phone (regex) ----
    for i, w in enumerate(words):
        if RE_PHONE.match(w) and len(re.sub(r"\D", "", w)) >= 10:
            _set_span(labels, i, i + 1, "vendor_phone")

    # ---- 11) Terms and conditions: "30 Days" after "Mode/Terms of Payment" ----
    i = _find_seq(words, ["Mode/Terms", "of", "Payment"])
    if i >= 0 and i + 3 < n:
        # take next 1-3 tokens that aren't a known anchor
        t_start = i + 3
        t_end = t_start
        while t_end < n and t_end - t_start < 4:
            w = words[t_end]
            if w in {"Other", "References", "Dispatched", "Dated", "Delivery"}:
                break
            t_end += 1
        if t_end > t_start:
            _set_span(labels, t_start, t_end, "terms_and_conditions")

    # ---- 12) Total quantity: the "1" right before "Service Call Charge"
    # Layout: ... "1" "Service" "Call" "Charge" ...
    i = _find_seq(words, ["Service", "Call", "Charge"])
    if i >= 1 and words[i - 1].isdigit() and labels[i - 1] == "O":
        _set_span(labels, i - 1, i, "total_quantity")

    return labels


@click.command()
@click.option("--in", "in_dir", type=click.Path(exists=True, file_okay=False),
              required=True, help="Directory containing .json files to relabel")
@click.option("--inplace", is_flag=True, help="Overwrite in place (otherwise dry-run)")
def main(in_dir: str, inplace: bool) -> None:
    src = Path(in_dir)
    jsons = sorted(src.glob("*.json"))
    if not jsons:
        raise SystemExit(f"No JSONs in {src}")

    total_words = 0
    labeled_words = 0
    field_counts: dict[str, int] = {}
    for jp in jsons:
        data = json.loads(jp.read_text(encoding="utf-8"))
        words = data["words"]
        new_labels = label_words(words)
        if len(new_labels) != len(words):
            log.error("Length mismatch on %s", jp.name); continue
        total_words += len(words)
        for lbl in new_labels:
            if lbl != "O":
                labeled_words += 1
                fld = lbl.split("-", 1)[1]
                field_counts[fld] = field_counts.get(fld, 0) + 1
        data["labels"] = new_labels
        if inplace:
            jp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("%s: %d/%d words labeled", jp.name, sum(1 for l in new_labels if l != "O"), len(words))

    log.info("---- Summary ----")
    log.info("Total words:    %d", total_words)
    log.info("Labeled words:  %d (%.1f%%)", labeled_words, 100 * labeled_words / max(1, total_words))
    log.info("Per-field counts:")
    for k in sorted(field_counts):
        log.info("  %-22s %d", k, field_counts[k])
    if not inplace:
        log.info("(dry-run; pass --inplace to write)")


if __name__ == "__main__":
    main()
