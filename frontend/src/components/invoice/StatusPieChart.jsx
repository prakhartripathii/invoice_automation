/**
 * StatusPieChart — donut chart of invoice counts by status, fed from
 * the same DashboardStats payload that powers the stat tiles.
 */
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

const SLICES = [
  { key: 'auto_approved', label: 'Auto-approved', color: '#16a34a' },
  { key: 'review_required', label: 'Needs review', color: '#d97706' },
  { key: 'posted', label: 'Posted', color: '#2563eb' },
  { key: 'failed', label: 'Failed', color: '#dc2626' },
];

export default function StatusPieChart({ stats }) {
  if (!stats) return null;

  const data = SLICES.map((s) => ({
    name: s.label,
    value: Number(stats[s.key] ?? 0),
    color: s.color,
  })).filter((d) => d.value > 0);

  const total = Number(stats.total ?? 0);

  if (!data.length) {
    return (
      <div className="muted" style={{ padding: 24, textAlign: 'center' }}>
        No invoices processed yet.
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={100}
            paddingAngle={2}
            label={({ value }) => value}
          >
            {data.map((d) => (
              <Cell key={d.name} fill={d.color} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value, name) => {
              const pct = total ? Math.round((value / total) * 100) : 0;
              return [`${value} (${pct}%)`, name];
            }}
          />
          <Legend verticalAlign="bottom" height={36} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
