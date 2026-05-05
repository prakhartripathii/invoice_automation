"""Invoice-related schemas."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.invoice import InvoiceStatus, LogLevel
from app.schemas.common import ORMModel


# ========== Line items ==========
class InvoiceItemBase(BaseModel):
    line_number: int = Field(..., ge=1)
    description: str = Field(..., min_length=1, max_length=1024)
    quantity: Decimal = Field(..., ge=0)
    unit_price: Decimal = Field(..., ge=0)
    amount: Decimal = Field(..., ge=0)
    tax_rate: Optional[Decimal] = Field(default=None, ge=0, le=100)


class InvoiceItemCreate(InvoiceItemBase):
    pass


class InvoiceItemRead(InvoiceItemBase, ORMModel):
    id: UUID


# ========== Invoice ==========
class InvoiceExtracted(BaseModel):
    """Shape of data extracted by an OCR agent."""
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Optional[str] = "USD"
    subtotal: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    purchase_order: Optional[str] = None
    items: List[InvoiceItemCreate] = Field(default_factory=list)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    raw: Dict[str, Any] = Field(default_factory=dict)


class InvoiceUpdate(BaseModel):
    """Fields editable by reviewers."""
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Optional[str] = None
    subtotal: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    purchase_order: Optional[str] = None
    review_notes: Optional[str] = None
    items: Optional[List[InvoiceItemCreate]] = None


class InvoiceUploadResponse(BaseModel):
    id: UUID
    original_filename: str
    status: InvoiceStatus
    message: str = "Invoice accepted for processing"


class ProcessingLogRead(ORMModel):
    id: UUID
    agent: str
    level: LogLevel
    message: str
    duration_ms: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None
    created_at: datetime


class InvoiceRead(ORMModel):
    id: UUID
    original_filename: str
    file_hash: str
    file_size_bytes: int
    mime_type: str

    vendor_name: Optional[str]
    invoice_number: Optional[str]
    invoice_date: Optional[date]
    due_date: Optional[date]
    currency: Optional[str]
    subtotal: Optional[Decimal]
    tax_amount: Optional[Decimal]
    total_amount: Optional[Decimal]
    purchase_order: Optional[str]

    confidence_score: Optional[Decimal]
    status: InvoiceStatus
    review_notes: Optional[str]
    error_message: Optional[str]
    retry_count: int

    sap_document_id: Optional[str]
    salesforce_vendor_id: Optional[str]
    posted_at: Optional[datetime]

    uploaded_by_id: UUID
    reviewed_by_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    items: List[InvoiceItemRead] = Field(default_factory=list)


class InvoiceDetail(InvoiceRead):
    """Full invoice with OCR comparison for the detail page."""
    champ_ocr_raw: Optional[Dict[str, Any]]
    challenger_ocr_raw: Optional[Dict[str, Any]]
    validation_report: Optional[Dict[str, Any]]
    logs: List[ProcessingLogRead] = Field(default_factory=list)


class InvoiceFilters(BaseModel):
    status: Optional[InvoiceStatus] = None
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    search: Optional[str] = None

    @field_validator("vendor_name", "invoice_number", "search")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class ReviewAction(BaseModel):
    action: str = Field(..., pattern="^(APPROVE|REJECT|REPROCESS)$")
    notes: Optional[str] = Field(default=None, max_length=2000)


# ========== Assets (per-unit) ==========
class InvoiceAssetBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    asset_name: Optional[str] = Field(default=None, max_length=512)
    brand: Optional[str] = Field(default=None, max_length=255)
    model_number: Optional[str] = Field(default=None, max_length=255)
    serial_number: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    base_amount: Optional[Decimal] = Field(default=None, ge=0)
    gst_amount: Optional[Decimal] = Field(default=None, ge=0)
    total_amount: Optional[Decimal] = Field(default=None, ge=0)
    warranty_start_date: Optional[date] = None
    warranty_end_date: Optional[date] = None


class InvoiceAssetRead(InvoiceAssetBase, ORMModel):
    id: UUID
    invoice_id: UUID
    invoice_item_id: UUID
    asset_index: int
    unit_index: int


class InvoiceAssetUpsert(InvoiceAssetBase):
    """Single asset row coming back from the form. `id` present if updating."""
    id: Optional[UUID] = None
    invoice_item_id: UUID
    asset_index: int = Field(..., ge=1)
    unit_index: int = Field(..., ge=1)


class AssetsSavePayload(BaseModel):
    assets: List[InvoiceAssetUpsert]


class ProductDetailsView(BaseModel):
    """Combined response for the Product Details page."""
    invoice_id: UUID
    invoice_number: Optional[str]
    vendor_name: Optional[str]
    currency: Optional[str]
    invoice_total: Optional[Decimal]
    items: List[InvoiceItemRead]
    assets: List[InvoiceAssetRead]


class AssetsValidationIssue(BaseModel):
    asset_index: int
    field: str
    message: str


class AssetsSaveResponse(BaseModel):
    assets: List[InvoiceAssetRead]
    invoice_total: Optional[Decimal]
    assets_total: Decimal
    totals_match: bool
    issues: List[AssetsValidationIssue] = Field(default_factory=list)
    updates: Optional[InvoiceUpdate] = None


class DashboardStats(BaseModel):
    total: int
    uploaded: int
    processing: int
    auto_approved: int
    review_required: int
    approved: int
    rejected: int
    posted: int
    failed: int
    processed_today: int
    avg_processing_seconds: float
