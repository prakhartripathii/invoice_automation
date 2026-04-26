import { STATUS_LABELS } from '../../constants/status.js';

export default function StatusBadge({ status }) {
  const klass = `badge badge--${(status || '').toLowerCase()}`;
  return <span className={klass}>{STATUS_LABELS[status] || status}</span>;
}
