/**
 * Product Details — turn each line item's quantity into N editable asset
 * cards. Assets are seeded server-side on first load.
 *
 * Route: /invoices/:id/product-details
 */
import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';

import { invoiceApi } from '../services/api.js';
import { SkeletonCard } from '../components/common/Skeleton.jsx';

const ASSET_FIELDS = [
  { key: 'asset_name', label: 'Asset Name', required: true, placeholder: 'Enter asset name' },
  { key: 'brand', label: 'Brand', placeholder: 'Enter brand' },
  { key: 'model_number', label: 'Model No.', placeholder: 'Enter model number' },
  { key: 'serial_number', label: 'Serial No.', placeholder: 'Enter serial number' },
];

const NUMERIC_FIELDS = [
  { key: 'base_amount', label: 'Base Amount' },
  { key: 'gst_amount', label: 'GST Amount' },
  { key: 'total_amount', label: 'Total Amount' },
];

const DATE_FIELDS = [
  { key: 'warranty_start_date', label: 'Warranty Start Date' },
  { key: 'warranty_end_date', label: 'Warranty End Date' },
];

function toInputDate(v) {
  if (!v) return '';
  // Backend returns ISO date (YYYY-MM-DD) — pass through.
  return String(v).slice(0, 10);
}

function fmtMoney(n, currency) {
  if (n == null || n === '') return '—';
  const num = Number(n);
  if (Number.isNaN(num)) return '—';
  return `${currency || ''} ${num.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`.trim();
}

export default function ProductDetails() {
  const { id } = useParams();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [issues, setIssues] = useState([]); // [{asset_index, field, message}]
  const [assets, setAssets] = useState([]);

  // Per-asset issue lookup for inline highlighting
  const issuesByAsset = useMemo(() => {
    const map = new Map();
    for (const i of issues) {
      if (!map.has(i.asset_index)) map.set(i.asset_index, []);
      map.get(i.asset_index).push(i);
    }
    return map;
  }, [issues]);

  const globalIssues = useMemo(
    () => issues.filter((i) => i.asset_index === 0),
    [issues],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    invoiceApi
      .productDetails(id)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setAssets(
          res.assets.map((a) => ({
            ...a,
            warranty_start_date: toInputDate(a.warranty_start_date),
            warranty_end_date: toInputDate(a.warranty_end_date),
          })),
        );
      })
      .catch((err) => {
        toast.error(err?.response?.data?.detail || 'Failed to load assets');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  // Auto-recalculate total_amount when base or gst changes (only if user
  // hasn't deliberately set total to a different value).
  const updateAsset = (index, patch) => {
    setAssets((prev) => {
      const next = [...prev];
      const merged = { ...next[index], ...patch };
      if ('base_amount' in patch || 'gst_amount' in patch) {
        const base = Number(merged.base_amount || 0);
        const gst = Number(merged.gst_amount || 0);
        if (!Number.isNaN(base) && !Number.isNaN(gst)) {
          merged.total_amount = (base + gst).toFixed(2);
        }
      }
      next[index] = merged;
      return next;
    });
  };

  const assetsTotal = useMemo(
    () =>
      assets.reduce((sum, a) => sum + (Number(a.total_amount) || 0), 0),
    [assets],
  );

  const totalsMatch = useMemo(() => {
    if (!data?.invoice_total) return true;
    return Math.abs(assetsTotal - Number(data.invoice_total)) <= 0.01;
  }, [assetsTotal, data]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = assets.map((a) => ({
        id: a.id,
        invoice_item_id: a.invoice_item_id,
        asset_index: a.asset_index,
        unit_index: a.unit_index,
        asset_name: a.asset_name || null,
        brand: a.brand || null,
        model_number: a.model_number || null,
        serial_number: a.serial_number || null,
        description: a.description || null,
        base_amount: a.base_amount === '' ? null : a.base_amount,
        gst_amount: a.gst_amount === '' ? null : a.gst_amount,
        total_amount: a.total_amount === '' ? null : a.total_amount,
        warranty_start_date: a.warranty_start_date || null,
        warranty_end_date: a.warranty_end_date || null,
      }));
      const res = await invoiceApi.saveAssets(id, payload);
      setIssues(res.issues || []);
      if (res.issues?.length) {
        toast.error(`Saved with ${res.issues.length} issue(s) — see highlights.`);
      } else {
        toast.success('Assets saved.');
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <>
        <SkeletonCard lines={3} />
        <div style={{ height: 16 }} />
        <SkeletonCard lines={6} />
      </>
    );
  }
  if (!data) {
    return <div className="empty-state">Product details unavailable.</div>;
  }

  const currency = data.currency || '';

  return (
    <>
      {/* ----- Top: invoice context ----- */}
      <div className="page-header">
        <div>
          <h1>Product Details</h1>
          <div className="page-header__subtitle">
            {data.invoice_number || '—'} · {data.vendor_name || 'Unknown vendor'}{' '}
            · Invoice total: {fmtMoney(data.invoice_total, currency)}
          </div>
        </div>
        <div className="row">
          <Link to={`/invoices/${id}`} className="btn btn--ghost">
            ← Back to invoice
          </Link>
          <button
            className="btn btn--primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving…' : 'Save assets'}
          </button>
        </div>
      </div>

      {/* ----- Validation banner ----- */}
      {(globalIssues.length > 0 || !totalsMatch) && (
        <div
          className="card"
          style={{
            borderColor: 'var(--color-warning, #d97706)',
            background: '#fef3c7',
            color: '#78350f',
            marginBottom: 16,
          }}
        >
          <strong>Validation:</strong>{' '}
          {!totalsMatch && (
            <span>
              Asset totals ({fmtMoney(assetsTotal, currency)}) don't match
              invoice total ({fmtMoney(data.invoice_total, currency)}).
            </span>
          )}
          {globalIssues.map((i, idx) => (
            <div key={idx}>{i.message}</div>
          ))}
        </div>
      )}

      {/* ----- Assets ----- */}
      <div className="card section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h2 className="card__title" style={{ margin: 0 }}>
            Assets{' '}
            <span className="badge badge--info" style={{ marginLeft: 8 }}>
              {assets.length} {assets.length === 1 ? 'Asset' : 'Assets'}
            </span>
          </h2>
          <div className="muted" style={{ fontSize: 13 }}>
            Sum of asset totals:{' '}
            <strong style={{ color: totalsMatch ? '#16a34a' : '#dc2626' }}>
              {fmtMoney(assetsTotal, currency)}
            </strong>
          </div>
        </div>

        {assets.length === 0 ? (
          <div className="empty-state" style={{ marginTop: 12 }}>
            No line items extracted — nothing to expand into assets.
          </div>
        ) : (
          <div className="stack" style={{ gap: 16, marginTop: 16 }}>
            {assets.map((a, idx) => {
              const issuesForRow = issuesByAsset.get(a.asset_index) || [];
              const issueFields = new Set(issuesForRow.map((i) => i.field));
              return (
                <div
                  key={a.id || `${a.asset_index}-${idx}`}
                  className="card"
                  style={{
                    borderColor: issuesForRow.length
                      ? 'var(--color-warning, #d97706)'
                      : undefined,
                  }}
                >
                  <h3 style={{ marginTop: 0 }}>Asset #{a.asset_index}</h3>

                  <div className="field-group__grid">
                    {ASSET_FIELDS.map((f) => (
                      <div className="form-control" key={f.key}>
                        <label>
                          {f.label}
                          {f.required && (
                            <span style={{ color: '#dc2626' }}> *</span>
                          )}
                          {issueFields.has(f.key) && (
                            <span style={{ color: '#a16207', marginLeft: 8 }}>
                              ⚠
                            </span>
                          )}
                        </label>
                        <input
                          className="input"
                          type="text"
                          value={a[f.key] ?? ''}
                          placeholder={f.placeholder}
                          onChange={(e) =>
                            updateAsset(idx, { [f.key]: e.target.value })
                          }
                        />
                      </div>
                    ))}
                  </div>

                  <div
                    className="field-group__grid"
                    style={{ marginTop: 12 }}
                  >
                    <div className="form-control form-control--full">
                      <label>Description</label>
                      <textarea
                        className="textarea"
                        rows={2}
                        value={a.description ?? ''}
                        placeholder="Enter description"
                        onChange={(e) =>
                          updateAsset(idx, { description: e.target.value })
                        }
                      />
                    </div>
                    {NUMERIC_FIELDS.map((f) => (
                      <div className="form-control" key={f.key}>
                        <label>
                          {f.label}
                          {issueFields.has(f.key) && (
                            <span style={{ color: '#a16207', marginLeft: 8 }}>
                              ⚠
                            </span>
                          )}
                        </label>
                        <input
                          className="input"
                          type="number"
                          step="0.01"
                          min="0"
                          value={a[f.key] ?? ''}
                          onChange={(e) =>
                            updateAsset(idx, { [f.key]: e.target.value })
                          }
                        />
                      </div>
                    ))}
                  </div>

                  <div
                    className="field-group__grid"
                    style={{ marginTop: 12 }}
                  >
                    {DATE_FIELDS.map((f) => (
                      <div className="form-control" key={f.key}>
                        <label>{f.label}</label>
                        <input
                          className="input"
                          type="date"
                          value={a[f.key] ?? ''}
                          onChange={(e) =>
                            updateAsset(idx, { [f.key]: e.target.value })
                          }
                        />
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
