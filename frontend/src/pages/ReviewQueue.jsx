/**
 * Review Queue — every invoice that is NOT yet finalized.
 * Shows: Processing, Review Required, Failed, Rejected.
 *
 * Adds color-coded status pills as a status filter, and inline Approve/Reject/Edit
 * actions per row.
 */
import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useNavigate } from 'react-router-dom';
import { format } from 'date-fns';

import StatusBadge from '../components/common/StatusBadge.jsx';
import { SkeletonTable } from '../components/common/Skeleton.jsx';
import {
  fetchInvoices,
  setFilter,
  submitReviewAction,
} from '../store/slices/invoicesSlice.js';
import {
  REVIEW_STATUSES,
  STATUS_LABELS,
  STATUS_COLORS,
} from '../constants/status.js';

export default function ReviewQueue() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { list, listStatus } = useSelector((s) => s.invoices);
  const [activeStatus, setActiveStatus] = useState(''); // '' = all review statuses
  const [actingId, setActingId] = useState(null);

  // Fetch a wide page on mount; we filter client-side by REVIEW_STATUSES.
  useEffect(() => {
    dispatch(setFilter({ status: '', page: 1, size: 100 }));
    dispatch(fetchInvoices());
  }, [dispatch]);

  const counts = useMemo(() => {
    const c = Object.fromEntries(REVIEW_STATUSES.map((s) => [s, 0]));
    for (const inv of list.items) {
      if (inv.status in c) c[inv.status] += 1;
    }
    return c;
  }, [list.items]);

  const visibleItems = useMemo(() => {
    const base = list.items.filter((i) => REVIEW_STATUSES.includes(i.status));
    return activeStatus ? base.filter((i) => i.status === activeStatus) : base;
  }, [list.items, activeStatus]);

  const totalReview = useMemo(
    () => list.items.filter((i) => REVIEW_STATUSES.includes(i.status)).length,
    [list.items],
  );

  const handleAction = async (invoiceId, action) => {
    setActingId(invoiceId);
    await dispatch(submitReviewAction({ invoiceId, payload: { action } }));
    await dispatch(fetchInvoices());
    setActingId(null);
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Review Queue</h1>
          <div className="page-header__subtitle">
            Invoices awaiting human action — {totalReview} total
          </div>
        </div>
      </div>

      {/* Color-coded status filter pills */}
      <div className="status-pills">
        <button
          type="button"
          className={`status-pill ${activeStatus === '' ? 'status-pill--active' : ''}`}
          onClick={() => setActiveStatus('')}
        >
          All <span className="status-pill__count">{totalReview}</span>
        </button>
        {REVIEW_STATUSES.map((s) => (
          <button
            key={s}
            type="button"
            className={`status-pill status-pill--${s.toLowerCase()} ${
              activeStatus === s ? 'status-pill--active' : ''
            }`}
            style={{ '--pill-color': STATUS_COLORS[s] }}
            onClick={() => setActiveStatus(s)}
          >
            {STATUS_LABELS[s]} <span className="status-pill__count">{counts[s]}</span>
          </button>
        ))}
      </div>

      {listStatus === 'loading' && visibleItems.length === 0 ? (
        <SkeletonTable />
      ) : visibleItems.length === 0 ? (
        <div className="empty-state">
          🎉 Nothing here — every invoice in scope has been actioned.
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Invoice #</th>
                <th>Vendor</th>
                <th>Amount</th>
                <th>Confidence</th>
                <th>Status</th>
                <th>Uploaded</th>
                <th style={{ width: 240 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleItems.map((inv) => {
                const busy = actingId === inv.id;
                const isFinal = inv.status === 'REJECTED';
                return (
                  <tr key={inv.id}>
                    <td>
                      <Link to={`/invoices/${inv.id}`}>
                        {inv.invoice_number || '—'}
                      </Link>
                    </td>
                    <td>{inv.vendor_name || '—'}</td>
                    <td>
                      {inv.total_amount
                        ? `${inv.currency || 'USD'} ${Number(inv.total_amount).toLocaleString()}`
                        : '—'}
                    </td>
                    <td>
                      {inv.confidence_score != null
                        ? `${(Number(inv.confidence_score) * 100).toFixed(1)}%`
                        : '—'}
                    </td>
                    <td>
                      <StatusBadge status={inv.status} />
                    </td>
                    <td className="muted">
                      {format(new Date(inv.created_at), 'MMM d, HH:mm')}
                    </td>
                    <td>
                      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          className="btn btn--success btn--sm"
                          disabled={busy || isFinal}
                          onClick={() => handleAction(inv.id, 'APPROVE')}
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          className="btn btn--danger btn--sm"
                          disabled={busy || isFinal}
                          onClick={() => handleAction(inv.id, 'REJECT')}
                        >
                          Reject
                        </button>
                        <button
                          type="button"
                          className="btn btn--ghost btn--sm"
                          onClick={() => navigate(`/invoices/${inv.id}`)}
                        >
                          Edit
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
