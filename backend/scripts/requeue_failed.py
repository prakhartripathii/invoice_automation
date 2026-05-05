"""Re-queue all invoices that finished processing with confidence < 0.3
or status REVIEW_REQUIRED and zero confidence — useful after fixing
an OCR bug to re-run the pipeline on the stuck ones.

Usage:  venv\Scripts\python.exe -m scripts.requeue_failed
"""
from app.db.session import SessionLocal
from app.db.models.invoice import Invoice, InvoiceStatus
from app.workers.tasks import process_invoice_task


def main() -> None:
    with SessionLocal() as db:
        stuck = (
            db.query(Invoice)
            .filter(
                (Invoice.confidence_score == None)  # noqa: E711
                | (Invoice.confidence_score < 0.3)
            )
            .all()
        )
        if not stuck:
            print("Nothing to requeue.")
            return
        for inv in stuck:
            print(f"requeue {inv.id}  status={inv.status}  conf={inv.confidence_score}")
            inv.status = InvoiceStatus.UPLOADED
        db.commit()

        for inv in stuck:
            process_invoice_task.apply_async(
                args=[str(inv.id)],
                task_id=f"invoice-{inv.id}",
            )
        print(f"Re-queued {len(stuck)} invoices.")


if __name__ == "__main__":
    main()
