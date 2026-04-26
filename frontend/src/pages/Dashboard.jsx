/**
 * Dashboard — analytics & summary only.
 * Upload, batch pie chart, and per-batch slicer have moved to /upload.
 */
import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';

import { SkeletonCard } from '../components/common/Skeleton.jsx';
import { fetchStats } from '../store/slices/invoicesSlice.js';

const STAT_CARDS = [
  { key: 'total', label: 'Total invoices', variant: 'primary' },
  { key: 'auto_approved', label: 'Auto-approved', variant: 'success' },
  { key: 'review_required', label: 'Needs review', variant: 'warning' },
  { key: 'failed', label: 'Failed', variant: 'danger' },
  { key: 'posted', label: 'Posted to SAP', variant: 'info' },
  { key: 'processed_today', label: 'Processed today', variant: 'primary' },
];

export default function Dashboard() {
  const dispatch = useDispatch();
  const { stats, statsStatus } = useSelector((s) => s.invoices);

  useEffect(() => {
    dispatch(fetchStats());
    const id = setInterval(() => dispatch(fetchStats()), 15000);
    return () => clearInterval(id);
  }, [dispatch]);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <div className="page-header__subtitle">
            Real-time overview of invoice processing pipeline
          </div>
        </div>
        <div className="row">
          <Link to="/upload" className="btn btn--primary">
            Upload invoices
          </Link>
          <Link to="/invoices" className="btn btn--secondary">
            View invoices
          </Link>
          <Link to="/review" className="btn btn--secondary">
            Review queue
          </Link>
        </div>
      </div>

      {!stats && statsStatus === 'loading' ? (
        <div className="stats-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} lines={2} />
          ))}
        </div>
      ) : (
        <div className="stats-grid">
          {STAT_CARDS.map((c) => (
            <div key={c.key} className={`stat-card stat-card--${c.variant}`}>
              <div className="stat-card__accent" />
              <div className="stat-card__label">{c.label}</div>
              <div className="stat-card__value">{stats?.[c.key] ?? 0}</div>
              {c.key === 'total' && (
                <div className="stat-card__delta">
                  Avg processing:{' '}
                  {stats?.avg_processing_seconds
                    ? `${stats.avg_processing_seconds.toFixed(1)}s`
                    : '—'}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="card section">
        <h2 className="card__title">Quick actions</h2>
        <div className="row">
          <Link to="/review" className="btn btn--secondary">
            Open review queue
          </Link>
          <Link to="/invoices?status=POSTED" className="btn btn--secondary">
            Recently posted
          </Link>
          <Link to="/invoices?status=APPROVED" className="btn btn--secondary">
            Approved invoices
          </Link>
        </div>
      </div>
    </>
  );
}
