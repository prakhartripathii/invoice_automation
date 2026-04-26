/**
 * Side-panel/modal that lists the invoices from a batch filtered by a status.
 * Opens when the user clicks a pie segment.
 */
import { Link } from 'react-router-dom';

import StatusBadge from '../common/StatusBadge.jsx';
import { STATUS_LABELS, routeForInvoice } from '../../constants/status.js';

export default function BatchSlicerPanel({ status, invoices, onClose }) {
  if (!status) return null;

  const filtered = (invoices || []).filter((i) => i.status === status);

  return (
    <div
      className="slicer-panel-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div className="slicer-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slicer-panel__header">
          <div>
            <div className="slicer-panel__title">
              {STATUS_LABELS[status] || status}
            </div>
            <div className="slicer-panel__subtitle">
              {filtered.length} invoice{filtered.length === 1 ? '' : 's'} in this slice
            </div>
          </div>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={onClose}
            aria-label="Close panel"
          >
            ✕
          </button>
        </div>

        {filtered.length === 0 ? (
          <div className="empty-state">No invoices match this slice.</div>
        ) : (
          <ul className="slicer-list">
            {filtered.map((inv) => (
              <li key={inv.id} className="slicer-list__item">
                <Link
                  to={routeForInvoice(inv)}
                  className="slicer-list__link"
                  onClick={onClose}
                >
                  <div className="slicer-list__main">
                    <div className="slicer-list__id">
                      {inv.invoice_number || inv.original_filename || inv.id}
                    </div>
                    <div className="slicer-list__vendor">
                      {inv.vendor_name || <span className="muted">Unknown vendor</span>}
                    </div>
                  </div>
                  <div className="slicer-list__meta">
                    <div className="slicer-list__amount">
                      {inv.total_amount
                        ? `${inv.currency || 'USD'} ${Number(inv.total_amount).toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                          })}`
                        : '—'}
                    </div>
                    <StatusBadge status={inv.status} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
