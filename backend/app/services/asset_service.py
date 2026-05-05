"""Asset service: explode line items into per-unit assets and persist edits.

Each line item with quantity=N becomes N InvoiceAsset rows. The split is
deterministic (asset_index 1..total) and stable across refreshes — the
existing rows are returned if they already exist.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.invoice import Invoice, InvoiceAsset, InvoiceItem
from app.schemas.invoice import (
    AssetsSaveResponse,
    AssetsValidationIssue,
    InvoiceAssetUpsert,
)
from app.utils.exceptions import NotFoundError


# ----- Constants -----
# We only allow integer quantities to drive asset splits; partial-unit invoices
# (e.g. 1.5 metres of cable) collapse to a single asset.
def _unit_count(qty: Decimal | None) -> int:
    if qty is None:
        return 1
    try:
        n = int(Decimal(qty))
    except Exception:
        return 1
    return max(1, n)


def _q(d: Decimal | None) -> Decimal:
    return Decimal(d) if d is not None else Decimal("0")


class AssetService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------- Loaders ----------
    def _load_invoice(self, invoice_id: UUID) -> Invoice:
        invoice = self.db.scalar(
            select(Invoice)
            .options(
                selectinload(Invoice.items),
                selectinload(Invoice.assets),
            )
            .where(Invoice.id == invoice_id)
        )
        if not invoice:
            raise NotFoundError(f"Invoice {invoice_id} not found")
        return invoice

    # ---------- Public API ----------
    def get_or_seed_for_invoice(self, invoice_id: UUID) -> Invoice:
        """Return the invoice with assets, seeding rows if none exist yet.

        Seeding rule: for each line item, create `quantity` (>=1) asset rows
        with prefilled fields derived from the item.
        """
        invoice = self._load_invoice(invoice_id)
        if invoice.assets:
            return invoice

        seeds: List[InvoiceAsset] = []
        asset_index = 1
        items_sorted = sorted(invoice.items, key=lambda i: i.line_number)
        for item in items_sorted:
            n = _unit_count(item.quantity)
            base_per_unit = _q(item.unit_price)
            # Approximate per-unit GST: spread item's tax across units.
            # Item-level tax_amount isn't stored separately — use tax_rate*base.
            gst_per_unit = (
                (base_per_unit * (item.tax_rate or Decimal("0")) / Decimal("100"))
                .quantize(Decimal("0.01"))
                if item.tax_rate is not None
                else None
            )
            total_per_unit = (
                (base_per_unit + gst_per_unit).quantize(Decimal("0.01"))
                if gst_per_unit is not None
                else base_per_unit.quantize(Decimal("0.01"))
            )
            for unit_idx in range(1, n + 1):
                seeds.append(
                    InvoiceAsset(
                        invoice_id=invoice.id,
                        invoice_item_id=item.id,
                        asset_index=asset_index,
                        unit_index=unit_idx,
                        asset_name=item.description[:512] if item.description else None,
                        description=item.description,
                        base_amount=base_per_unit.quantize(Decimal("0.01")),
                        gst_amount=gst_per_unit,
                        total_amount=total_per_unit,
                    )
                )
                asset_index += 1

        if seeds:
            self.db.add_all(seeds)
            self.db.commit()
            # Re-load to get DB-generated IDs and ordering
            invoice = self._load_invoice(invoice_id)
        return invoice

    def save_assets(
        self, invoice_id: UUID, payload: List[InvoiceAssetUpsert]
    ) -> AssetsSaveResponse:
        """Replace asset rows for an invoice with the user-edited payload.

        We don't allow adding NEW assets beyond what's been seeded — the only
        way to introduce assets is via line-item quantities. So existing rows
        are matched by id (if provided) or by (asset_index, invoice_item_id),
        updated in place, and any rows missing from the payload are deleted.
        """
        invoice = self._load_invoice(invoice_id)
        existing_by_id: Dict[UUID, InvoiceAsset] = {a.id: a for a in invoice.assets}
        existing_by_idx: Dict[int, InvoiceAsset] = {
            a.asset_index: a for a in invoice.assets
        }

        valid_item_ids = {i.id for i in invoice.items}
        seen_ids: set[UUID] = set()
        issues: List[AssetsValidationIssue] = []

        for upsert in payload:
            if upsert.invoice_item_id not in valid_item_ids:
                issues.append(
                    AssetsValidationIssue(
                        asset_index=upsert.asset_index,
                        field="invoice_item_id",
                        message="invoice_item_id does not belong to this invoice",
                    )
                )
                continue

            row = (
                existing_by_id.get(upsert.id)
                if upsert.id is not None
                else existing_by_idx.get(upsert.asset_index)
            )
            if row is None:
                # Caller is trying to add a new asset — disallowed.
                issues.append(
                    AssetsValidationIssue(
                        asset_index=upsert.asset_index,
                        field="asset_index",
                        message=(
                            "Cannot add new assets beyond the seeded "
                            "line-item splits"
                        ),
                    )
                )
                continue

            for f in (
                "asset_name",
                "brand",
                "model_number",
                "serial_number",
                "description",
                "base_amount",
                "gst_amount",
                "total_amount",
                "warranty_start_date",
                "warranty_end_date",
            ):
                setattr(row, f, getattr(upsert, f))
            seen_ids.add(row.id)

        # Per spec: don't allow extras, but we don't auto-delete missing rows
        # either — the form always renders all seeded slots. Any row not in the
        # payload is left untouched.

        # ---- Validation: assets total vs invoice total ----
        assets_total = sum((_q(a.total_amount) for a in invoice.assets), Decimal("0"))
        invoice_total = _q(invoice.total_amount)
        # 1-cent tolerance for rounding noise
        totals_match = abs(assets_total - invoice_total) <= Decimal("0.01")
        if not totals_match and invoice_total > 0:
            issues.append(
                AssetsValidationIssue(
                    asset_index=0,
                    field="total_amount",
                    message=(
                        f"Sum of asset totals ({assets_total}) does not match "
                        f"invoice total ({invoice_total})."
                    ),
                )
            )

        # Per-asset required-field highlights
        for a in invoice.assets:
            if not a.asset_name:
                issues.append(
                    AssetsValidationIssue(
                        asset_index=a.asset_index,
                        field="asset_name",
                        message="Asset Name is required.",
                    )
                )

        self.db.commit()
        # Reload for fresh ordering
        invoice = self._load_invoice(invoice_id)

        return AssetsSaveResponse(
            assets=[a for a in invoice.assets],  # ORMModel will validate
            invoice_total=invoice.total_amount,
            assets_total=assets_total,
            totals_match=totals_match,
            issues=issues,
        )
