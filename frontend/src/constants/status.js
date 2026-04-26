/**
 * Centralized invoice status definitions.
 * Single source of truth for labels, colors, and groupings.
 */

export const STATUSES = [
  'UPLOADED',
  'PROCESSING',
  'AUTO_APPROVED',
  'REVIEW_REQUIRED',
  'APPROVED',
  'POSTED',
  'REJECTED',
  'FAILED',
];

export const STATUS_LABELS = {
  UPLOADED: 'Uploaded',
  PROCESSING: 'Processing',
  AUTO_APPROVED: 'Auto Approved',
  REVIEW_REQUIRED: 'Review Required',
  APPROVED: 'Approved',
  POSTED: 'Posted',
  REJECTED: 'Rejected',
  FAILED: 'Failed',
};

/**
 * Color palette per the UX spec:
 *   Uploaded → Grey
 *   Processing → Purple/Blue
 *   Auto Approved → Green
 *   Review Required → Yellow
 *   Approved → Light Green
 *   Posted → Dark Blue
 *   Rejected → Red
 *   Failed → Dark Red
 */
export const STATUS_COLORS = {
  UPLOADED: '#64748b',         // grey
  PROCESSING: '#7c3aed',       // purple/blue
  AUTO_APPROVED: '#16a34a',    // green
  REVIEW_REQUIRED: '#ca8a04',  // yellow
  APPROVED: '#22c55e',         // light green
  POSTED: '#0c4a6e',           // dark blue
  REJECTED: '#dc2626',         // red
  FAILED: '#991b1b',           // dark red
};

/** Statuses shown on the View Invoices page. */
export const VIEW_STATUSES = ['APPROVED', 'POSTED'];

/** Statuses shown on the Review Queue page (everything not yet posted/finalized). */
export const REVIEW_STATUSES = ['PROCESSING', 'REVIEW_REQUIRED', 'FAILED', 'REJECTED'];

/**
 * Where should a click on an invoice in the slicer panel route to?
 * Approved/Posted → detail page; everything else → review (which uses detail page too,
 * but the URL semantics differ). Today both routes resolve to /invoices/:id.
 */
export function routeForInvoice(inv) {
  return `/invoices/${inv.id}`;
}
