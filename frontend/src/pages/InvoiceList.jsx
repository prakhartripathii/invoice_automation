/**
 * View Invoices — finalized invoices only (Approved + Posted).
 * Other statuses live in /review.
 */
import { Fragment, useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useSearchParams } from 'react-router-dom';
import { format } from 'date-fns';

import StatusBadge from '../components/common/StatusBadge.jsx';
import { SkeletonTable } from '../components/common/Skeleton.jsx';
import {
  fetchInvoices,
  resetFilters,
  setFilter,
} from '../store/slices/invoicesSlice.js';
import { VIEW_STATUSES, STATUS_LABELS } from '../constants/status.js';

export default function InvoiceList() {
  const dispatch = useDispatch();
  const [params] = useSearchParams();
  const { list, filters, listStatus } = useSelector((s) => s.invoices);
  const [expandedId, setExpandedId] = useState(null);

  const toggleExpand = (id, e) => {
    e.stopPropagation();
    setExpandedId((prev) => (prev === id ? null : id));
  };

  // On mount: pick up ?status= from URL (e.g. dashboard quick-link), but only
  // if it is an allowed view status; otherwise default the dropdown to "all view statuses".
  useEffect(() => {
    const statusParam = params.get('status');
    if (statusParam && VIEW_STATUSES.includes(statusParam)) {
      dispatch(setFilter({ status: statusParam, page: 1 }));
    } else {
      // Empty `status` filter — but the API call below will inject a multi-status filter.
      dispatch(setFilter({ status: '', page: 1 }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch whenever filters change. We always restrict to VIEW_STATUSES on the client side
  // by sending `status` if a single one is chosen, otherwise letting the server return all
  // and filtering client-side. (Backend may not support multi-status query in one call.)
  useEffect(() => {
    dispatch(fetchInvoices());
  }, [dispatch, filters]);

  const visibleItems = useMemo(() => {
    // If user picked a specific status, list already reflects it. Otherwise restrict
    // client-side to APPROVED + POSTED.
    if (filters.status) return list.items;
    return list.items.filter((i) => VIEW_STATUSES.includes(i.status));
  }, [list.items, filters.status]);

  const onFilter = (patch) => dispatch(setFilter(patch));

  return (
    <>
      <div className="page-header">
        <div>
          <h1>View Invoices</h1>
          <div className="page-header__subtitle">
            Approved & Posted invoices · {visibleItems.length} on this page
          </div>
        </div>
        <button className="btn btn--ghost" onClick={() => dispatch(resetFilters())}>
          Clear filters
        </button>
      </div>

      <div className="filter-bar">
        <input
          className="input"
          placeholder="Search vendor, invoice #, filename…"
          value={filters.search}
          onChange={(e) => onFilter({ search: e.target.value })}
        />
        <select
          className="select"
          value={filters.status}
          onChange={(e) => onFilter({ status: e.target.value })}
        >
          <option value="">All (Approved + Posted)</option>
          {VIEW_STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <input
          className="input"
          type="date"
          value={filters.date_from}
          onChange={(e) => onFilter({ date_from: e.target.value })}
        />
        <input
          className="input"
          type="date"
          value={filters.date_to}
          onChange={(e) => onFilter({ date_to: e.target.value })}
        />
        <select
          className="select"
          value={`${filters.sort_by}:${filters.sort_dir}`}
          onChange={(e) => {
            const [sort_by, sort_dir] = e.target.value.split(':');
            onFilter({ sort_by, sort_dir });
          }}
        >
          <option value="created_at:desc">Newest first</option>
          <option value="created_at:asc">Oldest first</option>
          <option value="total_amount:desc">Amount (high → low)</option>
          <option value="total_amount:asc">Amount (low → high)</option>
          <option value="vendor_name:asc">Vendor (A → Z)</option>
        </select>
      </div>

      {listStatus === 'loading' && visibleItems.length === 0 ? (
        <SkeletonTable />
      ) : visibleItems.length === 0 ? (
        <div className="empty-state">
          No approved or posted invoices yet.
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="table table--interactive">
            <thead>
              <tr>
                <th style={{ width: 36 }}></th>
                <th style={{ width: 60 }}>SNO.</th>
                <th>Invoice No.</th>
                <th>Vendor Name</th>
                <th>Date of Invoice</th>
                <th>Total Amount</th>
                <th>Status</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {visibleItems.map((inv, idx) => {
                const sno =
                  inv.sno ?? (list.page - 1) * (list.size || 20) + idx + 1;
                const isOpen = expandedId === inv.id;
                return (
                  <Fragment key={inv.id}>
                    <tr
                      onClick={() => (window.location.href = `/invoices/${inv.id}`)}
                    >
                      <td onClick={(e) => toggleExpand(inv.id, e)}>
                        <button
                          type="button"
                          className="row-toggle"
                          aria-expanded={isOpen}
                          aria-label={isOpen ? 'Collapse details' : 'Expand details'}
                          onClick={(e) => toggleExpand(inv.id, e)}
                        >
                          {isOpen ? '▾' : '▸'}
                        </button>
                      </td>
                      <td className="mono">{sno}</td>
                      <td>
                        <Link to={`/invoices/${inv.id}`}>
                          {inv.invoice_number || <span className="muted">—</span>}
                        </Link>
                        <div className="muted mono" style={{ fontSize: 11 }}>
                          {inv.original_filename}
                        </div>
                      </td>
                      <td>{inv.vendor_name || <span className="muted">—</span>}</td>
                      <td>
                        {inv.invoice_date
                          ? format(new Date(inv.invoice_date), 'MMM d, yyyy')
                          : '—'}
                      </td>
                      <td>
                        {inv.total_amount
                          ? `${inv.currency || 'USD'} ${Number(inv.total_amount).toLocaleString(undefined, {
                              minimumFractionDigits: 2,
                            })}`
                          : '—'}
                      </td>
                      <td>
                        <StatusBadge status={inv.status} />
                      </td>
                      <td className="muted">
                        {format(new Date(inv.created_at), 'MMM d, HH:mm')}
                      </td>
                    </tr>
                    {isOpen && (
                      <tr className="row-expanded">
                        <td colSpan={8} onClick={(e) => e.stopPropagation()}>
                          <div className="row-expanded__grid">
                            <div>
                              <div className="muted">Address</div>
                              <div>{inv.vendor_address || '—'}</div>
                            </div>
                            <div>
                              <div className="muted">Phone</div>
                              <div>{inv.vendor_phone || '—'}</div>
                            </div>
                            <div>
                              <div className="muted">Email</div>
                              <div>{inv.vendor_email || '—'}</div>
                            </div>
                            <div>
                              <div className="muted">PO No.</div>
                              <div>{inv.purchase_order || '—'}</div>
                            </div>
                            <div>
                              <div className="muted">Total Quantity</div>
                              <div>{inv.total_quantity ?? '—'}</div>
                            </div>
                            <div>
                              <div className="muted">GST</div>
                              <div>{inv.gst != null ? Number(inv.gst).toFixed(2) : '—'}</div>
                            </div>
                            <div>
                              <div className="muted">IGST</div>
                              <div>{inv.igst != null ? Number(inv.igst).toFixed(2) : '—'}</div>
                            </div>
                            <div>
                              <div className="muted">CGST</div>
                              <div>{inv.cgst != null ? Number(inv.cgst).toFixed(2) : '—'}</div>
                            </div>
                            <div className="row-expanded__terms">
                              <div className="muted">Terms &amp; Conditions</div>
                              <div>{inv.terms_and_conditions || '—'}</div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="pagination">
        <span className="pagination__info">
          Page {list.page} / {list.pages}
        </span>
        <button
          onClick={() => onFilter({ page: Math.max(1, list.page - 1) })}
          disabled={list.page <= 1}
        >
          Previous
        </button>
        <button
          onClick={() => onFilter({ page: Math.min(list.pages, list.page + 1) })}
          disabled={list.page >= list.pages}
        >
          Next
        </button>
      </div>
    </>
  );
}
