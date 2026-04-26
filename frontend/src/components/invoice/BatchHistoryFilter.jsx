/**
 * Dropdown listing every saved batch (most recent first).
 * Used above the pie chart to switch between batches.
 */
import { format } from 'date-fns';

export default function BatchHistoryFilter({ batches, activeBatchId, onSelect }) {
  if (!batches || batches.length === 0) return null;

  const value = activeBatchId || batches[0].id;

  return (
    <div className="batch-history">
      <label className="batch-history__label" htmlFor="batch-select">
        Batch:
      </label>
      <select
        id="batch-select"
        className="select"
        value={value}
        onChange={(e) => onSelect(e.target.value)}
      >
        {batches.map((b, idx) => (
          <option key={b.id} value={b.id}>
            {format(new Date(b.timestamp), 'MMM d, yyyy · HH:mm')} —{' '}
            {b.invoices.length}/{b.totalInvoices} invoice
            {b.totalInvoices === 1 ? '' : 's'}
            {idx === 0 ? ' (latest)' : ''}
          </option>
        ))}
      </select>
    </div>
  );
}
