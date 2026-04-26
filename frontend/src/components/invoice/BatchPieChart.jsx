/**
 * Donut chart of invoice statuses for a single batch.
 * Clicking a segment fires `onSegmentClick(status)` so the parent can open
 * the slicer panel.
 */
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import { STATUS_COLORS, STATUS_LABELS } from '../../constants/status.js';

function buildData(invoices) {
  const counts = {};
  for (const inv of invoices) {
    const s = inv.status || 'UPLOADED';
    counts[s] = (counts[s] || 0) + 1;
  }
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
  return Object.entries(counts)
    .map(([status, value]) => ({
      status,
      name: STATUS_LABELS[status] || status,
      value,
      pct: ((value / total) * 100).toFixed(1),
    }))
    .sort((a, b) => b.value - a.value);
}

export default function BatchPieChart({ invoices, onSegmentClick }) {
  const data = buildData(invoices || []);

  if (!data.length) {
    return (
      <div className="empty-state">
        No invoices in this batch yet.
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: 320 }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius={60}
            outerRadius={110}
            paddingAngle={2}
            onClick={(slice) => onSegmentClick && onSegmentClick(slice.status)}
            cursor="pointer"
          >
            {data.map((entry) => (
              <Cell key={entry.status} fill={STATUS_COLORS[entry.status] || '#94a3b8'} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value, _name, props) => [
              `${value} (${props.payload.pct}%)`,
              props.payload.name,
            ]}
          />
          <Legend
            verticalAlign="bottom"
            iconType="circle"
            formatter={(value, entry) => {
              const d = entry.payload;
              return `${value} — ${d.value} (${d.pct}%)`;
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
