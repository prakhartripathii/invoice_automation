import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useParams } from 'react-router-dom';
import { format } from 'date-fns';

import StatusBadge from '../components/common/StatusBadge.jsx';
import { SkeletonCard } from '../components/common/Skeleton.jsx';
import {
  clearCurrent,
  fetchInvoiceDetail,
  submitReviewAction,
} from '../store/slices/invoicesSlice.js';
import { formatMoney } from '../utils/money.js';

/**
 * Grouped extracted-field schema. Each group renders as its own subsection
 * inside the "Extracted fields" card.
 */
const FIELD_GROUPS = [
  {
    title: 'A. Basic Information',
    fields: [
      { key: 'sno', label: 'SNO.', readOnly: true },
      { key: 'invoice_number', label: 'Invoice No.' },
      { key: 'invoice_date', label: 'Date of Invoice', type: 'date' },
      { key: 'purchase_order', label: 'PO No.' },
    ],
  },
  {
    title: 'B. Vendor Details',
    fields: [
      { key: 'vendor_name', label: 'Vendor Name' },
      { key: 'vendor_address', label: 'Address' },
      { key: 'vendor_phone', label: 'Phone Number' },
      { key: 'vendor_email', label: 'Email', type: 'email' },
    ],
  },
  {
    title: 'C. Financial Details',
    fields: [
      { key: 'total_quantity', label: 'Total Quantity', type: 'number' },
      { key: 'gst', label: 'GST', type: 'number' },
      { key: 'igst', label: 'IGST', type: 'number' },
      { key: 'cgst', label: 'CGST', type: 'number' },
      { key: 'total_amount', label: 'Total Amount', type: 'number' },
    ],
  },
  {
    title: 'D. Additional Information',
    fields: [
      { key: 'terms_and_conditions', label: 'Terms & Conditions', type: 'textarea' },
    ],
  },
];


function asInputDate(v) {
  if (!v) return '';
  try {
    return format(new Date(v), 'yyyy-MM-dd');
  } catch {
    return '';
  }
}

export default function InvoiceDetail() {
  const { id } = useParams();
  const dispatch = useDispatch();
  const { current, currentStatus } = useSelector((s) => s.invoices);
  const displayCurrency = useSelector((s) => s.ui.currency);
  const [form, setForm] = useState({});
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    dispatch(fetchInvoiceDetail(id));
    return () => dispatch(clearCurrent());
  }, [dispatch, id]);

  useEffect(() => {
    if (current) {
      setForm({
        sno: current.sno ?? '',
        vendor_name: current.vendor_name || '',
        vendor_address: current.vendor_address || '',
        vendor_phone: current.vendor_phone || '',
        vendor_email: current.vendor_email || '',
        invoice_number: current.invoice_number || '',
        invoice_date: asInputDate(current.invoice_date),
        purchase_order: current.purchase_order || '',
        total_quantity: current.total_quantity ?? '',
        gst: current.gst ?? current.tax_amount ?? '',
        igst: current.igst ?? '',
        cgst: current.cgst ?? '',
        total_amount: current.total_amount ?? '',
        terms_and_conditions: current.terms_and_conditions || '',
      });
      setNotes(current.review_notes || '');
    }
  }, [current]);

  if (!current) {
    return currentStatus === 'loading' ? (
      <>
        <SkeletonCard lines={4} />
        <div style={{ height: 16 }} />
        <SkeletonCard lines={6} />
      </>
    ) : (
      <div className="empty-state">Invoice not found.</div>
    );
  }

  const handleAction = async (action) => {
    setSaving(true);
    const dirty =
      form.vendor_name !== (current.vendor_name || '') ||
      form.invoice_number !== (current.invoice_number || '') ||
      asInputDate(current.invoice_date) !== form.invoice_date ||
      String(current.total_amount || '') !== String(form.total_amount);
    const payload = {
      action,
      notes: notes || undefined,
      updates: dirty
        ? {
            vendor_name: form.vendor_name || null,
            vendor_address: form.vendor_address || null,
            vendor_phone: form.vendor_phone || null,
            vendor_email: form.vendor_email || null,
            invoice_number: form.invoice_number || null,
            invoice_date: form.invoice_date || null,
            purchase_order: form.purchase_order || null,
            total_quantity: form.total_quantity || null,
            gst: form.gst || null,
            igst: form.igst || null,
            cgst: form.cgst || null,
            tax_amount: form.gst || null,
            total_amount: form.total_amount || null,
            terms_and_conditions: form.terms_and_conditions || null,
          }
        : undefined,
    };
    await dispatch(submitReviewAction({ invoiceId: current.id, payload }));
    setSaving(false);
  };

  const canReview =
    current.status === 'REVIEW_REQUIRED' || current.status === 'FAILED';

  return (
    <>
      <div className="page-header">
        <div>
          <h1>
            {current.invoice_number || 'Unknown invoice'}{' '}
            <StatusBadge status={current.status} />
          </h1>
          <div className="page-header__subtitle">
            {current.original_filename} · Uploaded{' '}
            {format(new Date(current.created_at), 'MMM d, yyyy HH:mm')}
          </div>
        </div>
        <div className="row">
          <Link to="/invoices" className="btn btn--ghost">
            ← Back
          </Link>
        </div>
      </div>

      {current.error_message && (
        <div className="card" style={{ borderColor: 'var(--color-danger)', background: 'var(--color-danger-soft)', color: '#7f1d1d' }}>
          <strong>Error:</strong> {current.error_message}
        </div>
      )}

      <div className="grid-2 section">
        <div className="card">
          <h2 className="card__title">Extracted fields</h2>
          {FIELD_GROUPS.map((group) => (
            <div className="field-group" key={group.title}>
              <h3 className="field-group__title">{group.title}</h3>
              <div className="field-group__grid">
                {group.fields.map((f) => {
                  const disabled =
                    f.readOnly ||
                    (!canReview && current.status !== 'APPROVED');
                  const value = form[f.key] ?? '';
                  return (
                    <div
                      className={`form-control ${
                        f.type === 'textarea' ? 'form-control--full' : ''
                      }`}
                      key={f.key}
                    >
                      <label>{f.label}</label>
                      {f.type === 'textarea' ? (
                        <textarea
                          className="textarea"
                          rows={4}
                          value={value}
                          onChange={(e) =>
                            setForm({ ...form, [f.key]: e.target.value })
                          }
                          disabled={disabled}
                        />
                      ) : (
                        <input
                          className="input"
                          type={f.type || 'text'}
                          value={value}
                          onChange={(e) =>
                            setForm({ ...form, [f.key]: e.target.value })
                          }
                          disabled={disabled}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="stack">
          <div className="card">
            <h2 className="card__title">Validation report</h2>
            {current.validation_report ? (
              <>
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <div>
                    <div className="muted">Decision</div>
                    <strong>
                      {current.validation_report.decision || '—'}
                    </strong>
                  </div>
                  <div>
                    <div className="muted">Confidence</div>
                    <strong>
                      {(current.validation_report.weighted_confidence ?? 0) * 100}%
                    </strong>
                  </div>
                  <div>
                    <div className="muted">Agreement</div>
                    <strong>
                      {Math.round(
                        (current.validation_report.agreement_ratio ?? 0) * 100,
                      )}
                      %
                    </strong>
                  </div>
                </div>
                {current.validation_report.reasons?.length ? (
                  <ul style={{ marginTop: 12, paddingLeft: 20 }}>
                    {current.validation_report.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                ) : null}
              </>
            ) : (
              <div className="muted">No validation report yet.</div>
            )}
          </div>

          {canReview && (
            <div className="card">
              <h2 className="card__title">Review action</h2>
              <div className="form-control">
                <label>Notes (optional)</label>
                <textarea
                  className="textarea"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Add context about this decision…"
                />
              </div>
              <div className="row">
                <button
                  className="btn btn--success"
                  disabled={saving}
                  onClick={() => handleAction('APPROVE')}
                >
                  Approve &amp; post
                </button>
                <button
                  className="btn btn--danger"
                  disabled={saving}
                  onClick={() => handleAction('REJECT')}
                >
                  Reject
                </button>
                <button
                  className="btn btn--secondary"
                  disabled={saving}
                  onClick={() => handleAction('REPROCESS')}
                >
                  Reprocess
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="card section">
        <h2 className="card__title">Line items</h2>
        {current.items?.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Description</th>
                <th>Qty</th>
                <th>Unit price</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {current.items
                .slice()
                .sort((a, b) => a.line_number - b.line_number)
                .map((i) => (
                  <tr key={i.id}>
                    <td>{i.line_number}</td>
                    <td>{i.description}</td>
                    <td>{Number(i.quantity).toString()}</td>
                    <td>{formatMoney(i.unit_price, current.currency || 'USD', displayCurrency)}</td>
                    <td>{formatMoney(i.amount, current.currency || 'USD', displayCurrency)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        ) : (
          <div className="muted">No line items extracted.</div>
        )}
      </div>

    </>
  );
}
