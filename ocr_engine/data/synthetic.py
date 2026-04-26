"""Synthetic invoice generator — produces labeled PDF/PNG invoices with known ground truth.

Uses reportlab (vector-perfect layout + exact word coordinates), so no OCR errors corrupt the
labels. This gives you millions of samples in minutes to bootstrap the model.
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .converters import save_internal_example

log = logging.getLogger(__name__)


@dataclass
class InvoiceTemplate:
    """One invoice design (fonts, column layout, currency)."""

    name: str
    font: str = "Helvetica"
    font_size: int = 10
    currency: str = "USD"


DEFAULT_TEMPLATES: list[InvoiceTemplate] = [
    InvoiceTemplate(name="modern_usd", font="Helvetica", currency="USD"),
    InvoiceTemplate(name="classic_eur", font="Times-Roman", currency="EUR"),
    InvoiceTemplate(name="compact_inr", font="Courier", currency="INR"),
]


class SyntheticInvoiceGenerator:
    def __init__(self, seed: int | None = None, templates: Iterable[InvoiceTemplate] | None = None) -> None:
        self.random = random.Random(seed)
        try:
            from faker import Faker  # type: ignore
        except ImportError as e:
            raise ImportError("Faker is required. `pip install Faker`") from e
        self.faker = Faker()
        if seed is not None:
            Faker.seed(seed)
        self.templates = list(templates or DEFAULT_TEMPLATES)

    def generate_batch(self, count: int, out_dir: str | Path) -> int:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        written = 0
        for i in range(count):
            stem = f"synthetic_{i:06d}"
            try:
                self._render_one(stem, out)
                written += 1
            except Exception as e:  # pragma: no cover
                log.warning("Skipping %s: %s", stem, e)
        log.info("Generated %d synthetic invoices in %s", written, out)
        return written

    # -----------------------------------------------------
    # Rendering — one invoice → PNG + JSON with true labels
    # -----------------------------------------------------

    def _sample_invoice_data(self) -> dict[str, str | list[dict]]:
        vendor = self.faker.company()
        subtotal = round(self.random.uniform(50, 5000), 2)
        tax = round(subtotal * self.random.choice([0.05, 0.08, 0.1, 0.18]), 2)
        total = round(subtotal + tax, 2)
        line_items = []
        n_items = self.random.randint(1, 5)
        remaining = subtotal
        for idx in range(n_items):
            qty = self.random.randint(1, 10)
            unit_price = round(self.random.uniform(5, 500), 2)
            amount = round(qty * unit_price, 2)
            line_items.append(
                {
                    "desc": self.faker.catch_phrase().replace(",", "")[:40],
                    "qty": qty,
                    "unit_price": unit_price,
                    "amount": amount,
                }
            )
            remaining -= amount
        return {
            "vendor_name": vendor,
            "vendor_address": self.faker.address().replace("\n", ", "),
            "invoice_number": f"INV-{self.random.randint(10000, 999999)}",
            "invoice_date": self.faker.date_this_year().isoformat(),
            "due_date": self.faker.date_between(start_date="+1d", end_date="+60d").isoformat(),
            "purchase_order": f"PO-{self.random.randint(1000, 99999)}",
            "subtotal": f"{subtotal:.2f}",
            "tax_amount": f"{tax:.2f}",
            "total_amount": f"{total:.2f}",
            "line_items": line_items,
        }

    def _render_one(self, stem: str, out: Path) -> None:
        try:
            from reportlab.lib.pagesizes import letter  # type: ignore
            from reportlab.pdfgen import canvas  # type: ignore
        except ImportError as e:
            raise ImportError("reportlab is required. `pip install reportlab`") from e
        try:
            from pdf2image import convert_from_bytes  # type: ignore
        except ImportError as e:
            raise ImportError("pdf2image is required (needs poppler on PATH)") from e

        tpl = self.random.choice(self.templates)
        data = self._sample_invoice_data()

        import io

        buf = io.BytesIO()
        page_w, page_h = letter
        c = canvas.Canvas(buf, pagesize=letter)
        c.setFont(tpl.font, tpl.font_size)

        words: list[str] = []
        bboxes: list[list[int]] = []
        labels: list[str] = []

        def draw(text: str, x: float, y: float, field: str | None = None, is_start: bool = True) -> None:
            parts = str(text).split()
            cursor = x
            for i, part in enumerate(parts):
                w = c.stringWidth(part, tpl.font, tpl.font_size)
                # reportlab origin is bottom-left; flip to top-left for standard image coords
                bbox_pdf = (cursor, y, cursor + w, y + tpl.font_size)
                x0, y0 = bbox_pdf[0], page_h - bbox_pdf[3]
                x1, y1 = bbox_pdf[2], page_h - bbox_pdf[1]
                # Page coords are in points; we'll scale to image pixels after rasterization.
                words.append(part)
                bboxes.append([int(x0), int(y0), int(x1), int(y1)])
                if field:
                    tag = "B" if (is_start and i == 0) else "I"
                    labels.append(f"{tag}-{field.upper()}")
                else:
                    labels.append("O")
                c.drawString(cursor, y, part)
                cursor += w + c.stringWidth(" ", tpl.font, tpl.font_size)

        # --- Header
        c.setFont(tpl.font + "-Bold" if tpl.font == "Helvetica" else tpl.font, 18)
        c.drawString(72, page_h - 72, "INVOICE")
        c.setFont(tpl.font, tpl.font_size)

        y = page_h - 120
        draw(str(data["vendor_name"]), 72, y, field="vendor_name")
        y -= 16
        draw(str(data["vendor_address"]), 72, y, field="vendor_address")
        y -= 30

        # Invoice meta (right aligned column)
        x_right = 350
        draw("Invoice #:", x_right, y); draw(str(data["invoice_number"]), x_right + 80, y, field="invoice_number")
        y -= 14
        draw("Date:", x_right, y); draw(str(data["invoice_date"]), x_right + 80, y, field="invoice_date")
        y -= 14
        draw("Due:", x_right, y); draw(str(data["due_date"]), x_right + 80, y, field="due_date")
        y -= 14
        draw("PO:", x_right, y); draw(str(data["purchase_order"]), x_right + 80, y, field="purchase_order")

        # --- Line items
        y -= 40
        draw("Description", 72, y); draw("Qty", 320, y); draw("Unit", 380, y); draw("Amount", 460, y)
        y -= 18
        for li in data["line_items"]:  # type: ignore[assignment]
            draw(li["desc"], 72, y, field="line_item_description")
            draw(str(li["qty"]), 320, y, field="line_item_quantity")
            draw(f"{li['unit_price']:.2f}", 380, y, field="line_item_unit_price")
            draw(f"{li['amount']:.2f}", 460, y, field="line_item_amount")
            y -= 14

        # --- Totals
        y -= 20
        draw("Subtotal:", 380, y); draw(str(data["subtotal"]), 460, y, field="subtotal")
        y -= 14
        draw("Tax:", 380, y); draw(str(data["tax_amount"]), 460, y, field="tax_amount")
        y -= 14
        draw("Total:", 380, y); draw(str(data["total_amount"]), 460, y, field="total_amount")

        c.showPage()
        c.save()

        # Rasterize → PNG
        pdf_bytes = buf.getvalue()
        images = convert_from_bytes(pdf_bytes, dpi=150)
        if not images:
            raise RuntimeError("pdf2image returned no pages")
        pil = images[0]
        img_path = out / f"{stem}.png"
        pil.save(img_path, "PNG")

        # Scale boxes from points (72 dpi) to pixels (150 dpi)
        scale = 150 / 72
        scaled = [
            [int(x0 * scale), int(y0 * scale), int(x1 * scale), int(y1 * scale)]
            for (x0, y0, x1, y1) in bboxes
        ]

        save_internal_example(
            {
                "image": img_path.name,
                "words": words,
                "bboxes": scaled,
                "labels": labels,
                "image_size": [pil.width, pil.height],
                "currency": tpl.currency,
            },
            out / f"{stem}.json",
        )
