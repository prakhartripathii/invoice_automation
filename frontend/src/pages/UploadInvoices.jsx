/**
 * Upload Invoices page — dedicated upload + batch analytics view.
 *
 * Layout:
 *   - Page header
 *   - Upload dropzone (full-width card)
 *   - Batch history filter dropdown
 *   - Donut pie chart of the active batch's status distribution
 *   - Click a slice → BatchSlicerPanel modal with filtered invoices
 */
import { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { format } from 'date-fns';

import UploadDropzone from '../components/invoice/UploadDropzone.jsx';
import BatchPieChart from '../components/invoice/BatchPieChart.jsx';
import BatchSlicerPanel from '../components/invoice/BatchSlicerPanel.jsx';
import BatchHistoryFilter from '../components/invoice/BatchHistoryFilter.jsx';
import {
  appendInvoiceToBatch,
  selectActiveBatch,
  selectAllBatches,
  setActiveBatch,
  startBatch,
} from '../store/slices/batchesSlice.js';
import { STATUSES } from '../constants/status.js';

/* ------------------------------------------------------------------
 *  Demo data — used only by the "Load demo batch" button.
 *  Generates 24 fake invoices spread across all 8 statuses so the
 *  pie chart and slicer can be exercised without uploading real files.
 * ------------------------------------------------------------------ */
const DEMO_VENDORS = [
  'Acme Corp', 'Globex Inc.', 'Initech', 'Umbrella Co.',
  'Stark Industries', 'Wayne Enterprises', 'Soylent Corp',
  'Cyberdyne Systems', 'Tyrell Corporation', 'Wonka Industries',
];

const DEMO_CITIES = ['Mumbai', 'Bengaluru', 'Delhi', 'Pune', 'Hyderabad', 'Chennai'];
const DEMO_TERMS = [
  'Payment due within 30 days. Late payments incur 1.5% monthly interest.',
  'Net 15 terms. Goods remain property of seller until paid in full.',
  'Payment by bank transfer only. No returns after 7 days from delivery.',
  'Net 45. Disputes must be raised within 10 days of invoice date.',
];

function makeDemoInvoices() {
  // Distribution per status — gives an obviously-uneven pie
  const dist = {
    UPLOADED: 2,
    PROCESSING: 3,
    AUTO_APPROVED: 4,
    REVIEW_REQUIRED: 5,
    APPROVED: 3,
    POSTED: 4,
    REJECTED: 1,
    FAILED: 2,
  };

  const out = [];
  let n = 1;
  for (const status of STATUSES) {
    const count = dist[status] || 0;
    for (let i = 0; i < count; i++) {
      const vendor = DEMO_VENDORS[(n - 1) % DEMO_VENDORS.length];
      const slug = vendor.toLowerCase().replace(/[^a-z]+/g, '');
      const total = Math.round((50 + Math.random() * 4950) * 100) / 100;
      const gst = Math.round(total * 0.09 * 100) / 100;
      const cgst = Math.round(total * 0.045 * 100) / 100;
      const igst = Math.round(total * 0.09 * 100) / 100;
      out.push({
        id: `demo_${n}_${status.toLowerCase()}`,
        sno: n,
        invoice_number: `INV-${String(1000 + n).padStart(5, '0')}`,
        original_filename: `invoice_${n}.pdf`,
        vendor_name: vendor,
        vendor_address: `${100 + n} Market Street, ${DEMO_CITIES[n % DEMO_CITIES.length]}`,
        vendor_phone: `+1-555-${String(1000 + n).slice(-4)}`,
        vendor_email: `accounts@${slug}.com`,
        purchase_order: `PO-${8000 + n}`,
        status,
        currency: 'USD',
        total_amount: total,
        gst,
        igst,
        cgst,
        tax_amount: gst,
        total_quantity: Math.max(1, Math.floor(Math.random() * 50)),
        terms_and_conditions: DEMO_TERMS[n % DEMO_TERMS.length],
        confidence_score: Math.round((0.7 + Math.random() * 0.3) * 1000) / 1000,
        invoice_date: new Date(Date.now() - n * 86400000).toISOString(),
        created_at: new Date(Date.now() - n * 3600000).toISOString(),
      });
    }
    n += count;
  }
  return out;
}

export default function UploadInvoices() {
  const dispatch = useDispatch();
  const batches = useSelector(selectAllBatches);
  const activeBatch = useSelector(selectActiveBatch);
  const activeBatchId = useSelector((s) => s.batches.activeBatchId);

  const [slicerStatus, setSlicerStatus] = useState(null);

  const onSelectBatch = (id) => dispatch(setActiveBatch(id));

  const onLoadDemo = () => {
    const invoices = makeDemoInvoices();
    const action = dispatch(startBatch(invoices.length));
    const batchId = action.payload.id;
    for (const inv of invoices) {
      dispatch(appendInvoiceToBatch({ batchId, invoice: inv }));
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Upload Invoices</h1>
          <div className="page-header__subtitle">
            Drop files to start a new batch — track each batch's status distribution below.
          </div>
        </div>
        <button type="button" className="btn btn--ghost" onClick={onLoadDemo}>
          Load demo batch
        </button>
      </div>

      {/* ---------- Upload dropzone ---------- */}
      <div className="card">
        <UploadDropzone />
      </div>

      {/* ---------- Batch analytics ---------- */}
      <div className="card section">
        <div className="card__header-row">
          <div>
            <h2 className="card__title">Status distribution</h2>
            {activeBatch && (
              <div className="card__subtitle">
                {format(new Date(activeBatch.timestamp), 'MMM d, yyyy · HH:mm')} ·{' '}
                {activeBatch.invoices.length}/{activeBatch.totalInvoices} invoice
                {activeBatch.totalInvoices === 1 ? '' : 's'}
              </div>
            )}
          </div>
          <BatchHistoryFilter
            batches={batches}
            activeBatchId={activeBatchId}
            onSelect={onSelectBatch}
          />
        </div>

        {!activeBatch || activeBatch.invoices.length === 0 ? (
          <div className="empty-state">
            No batch data yet — drop some invoices above, or click{' '}
            <strong>Load demo batch</strong> in the header to see the chart.
          </div>
        ) : (
          <BatchPieChart
            invoices={activeBatch.invoices}
            onSegmentClick={(status) => setSlicerStatus(status)}
          />
        )}
      </div>

      {/* ---------- Slicer modal ---------- */}
      <BatchSlicerPanel
        status={slicerStatus}
        invoices={activeBatch?.invoices || []}
        onClose={() => setSlicerStatus(null)}
      />
    </>
  );
}
