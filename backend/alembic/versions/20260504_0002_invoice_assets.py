"""Add invoice_assets table for per-unit asset tracking.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_assets",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "invoice_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invoice_item_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoice_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asset_index", sa.Integer(), nullable=False),
        sa.Column("unit_index", sa.Integer(), nullable=False),
        sa.Column("asset_name", sa.String(length=512)),
        sa.Column("brand", sa.String(length=255)),
        sa.Column("model_number", sa.String(length=255)),
        sa.Column("serial_number", sa.String(length=255)),
        sa.Column("description", sa.Text()),
        sa.Column("base_amount", sa.Numeric(14, 2)),
        sa.Column("gst_amount", sa.Numeric(14, 2)),
        sa.Column("total_amount", sa.Numeric(14, 2)),
        sa.Column("warranty_start_date", sa.Date()),
        sa.Column("warranty_end_date", sa.Date()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_invoice_assets_invoice_id", "invoice_assets", ["invoice_id"]
    )
    op.create_index(
        "ix_invoice_assets_invoice_item_id",
        "invoice_assets",
        ["invoice_item_id"],
    )
    op.create_index(
        "ix_invoice_assets_invoice_index",
        "invoice_assets",
        ["invoice_id", "asset_index"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invoice_assets_invoice_index", table_name="invoice_assets"
    )
    op.drop_index(
        "ix_invoice_assets_invoice_item_id", table_name="invoice_assets"
    )
    op.drop_index("ix_invoice_assets_invoice_id", table_name="invoice_assets")
    op.drop_table("invoice_assets")
