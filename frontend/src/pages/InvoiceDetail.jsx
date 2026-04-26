import { useEffect, useMemo, useState } from 'react';
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

  const mismatches = useMemo(() => {
    if (!current?.validation_report?.fields) return {};
    const out = {};
    for (const [k, v] of Object.entries(current.validation_report.fields)) {
      if (!v.match) out[k] = true;
    }
    return out;
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
                      } ${mismatches[f.key] ? 'ocr-field--mismatch' : ''}`}
                      key={f.key}
                    >
                      <label>
                        {f.label}
                        {mismatches[f.key] && (
                          <span style={{ color: '#a16207', marginLeft: 8 }}>
                            ⚠ OCR mismatch
                          </span>
                        )}
                      </label>
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

      <div className="section">
        <h2 className="card__title" style={{ marginLeft: 4 }}>
          Champ vs Challenger
        </h2>
        <div className="ocr-compare">
          <OcrPanel
            title="Champ"
            data={current.champ_ocr_raw}
            mismatches={mismatches}
            sourceCurrency={current.currency || 'USD'}
            displayCurrency={displayCurrency}
          />
          <OcrPanel
            title="Challenger"
            data={current.challenger_ocr_raw}
            mismatches={mismatches}
            sourceCurrency={current.currency || 'USD'}
            displayCurrency={displayCurrency}
          />
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

      <div className="card section">
        <h2 className="card__title">Processing audit trail</h2>
        {current.logs?.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Agent</th>
                <th>Level</th>
                <th>Message</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              {current.logs.map((l) => (
                <tr key={l.id}>
                  <td className="muted mono">
                    {format(new Date(l.created_at), 'HH:mm:ss.SSS')}
                  </td>
                  <td>{l.agent}</td>
                  <td>
                    <span className={`badge badge--${l.level.toLowerCase()}`}>
                      {l.level}
                    </span>
                  </td>
                  <td>{l.message}</td>
                  <td className="muted">{l.duration_ms ? `${l.duration_ms} ms` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="muted">No processing logs yet.</div>
        )}
      </div>
    </>
  );
}

function OcrPanel({ title, data, mismatches, sourceCurrency = 'USD', displayCurrency = 'USD' }) {
  const fields = [
    ['vendor_name', 'Vendor'],
    ['invoice_number', 'Invoice #'],
    ['invoice_date', 'Date'],
    ['subtotal', 'Subtotal', 'money'],
    ['tax_amount', 'Tax', 'money'],
    ['total_amount', 'Total', 'money'],
    ['purchase_order', 'PO'],
  ];
  return (
    <div className="ocr-compare__col">
      <h4>{title}</h4>
      {data ? (
        fields.map(([k, label, kind]) => (
          <div
            key={k}
            className={`ocr-field ${mismatches[k] ? 'ocr-field--mismatch' : ''}`}
          >
            <span className="ocr-field__label">{label}</span>
            <span className="ocr-field__value">
              {kind === 'money'
                ? formatMoney(data[k], sourceCurrency, displayCurrency)
                : formatCell(data[k])}
            </span>
          </div>
        ))
      ) : (
        <div className="muted">No output (engine unavailable).</div>
      )}
      {data?.confidence_scores && (
        <div className="muted" style={{ marginTop: 12, fontSize: 12 }}>
          Avg confidence:{' '}
          {(
            Object.values(data.confidence_scores).reduce((a, b) => a + (b || 0), 0) /
            Math.max(1, Object.keys(data.confidence_scores).length)
          ).toFixed(2)}
        </div>
      )}
    </div>
  );
}

function formatCell(v) {
  if (v == null || v === '') return '—';
  if (typeof v === 'number') return v.toFixed(2);
  return String(v);
}
