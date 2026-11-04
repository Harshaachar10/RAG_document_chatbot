import { Link } from 'react-router-dom';
import type { KpiCard as Kpi } from '../api/contracts';

function buildHref(kpi: Kpi): string {
  const params = new URLSearchParams();
  Object.entries(kpi.filters || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v));
  });
  const qs = params.toString();
  return qs ? `${kpi.href}?${qs}` : kpi.href;
}

export function KpiCard({ kpi }: { kpi: Kpi }) {
  return (
    <Link
      to={buildHref(kpi)}
      className="block rounded-[12px] border border-border bg-white p-4 shadow-sm transition hover:border-accent hover:shadow"
      title={kpi.tooltip}
    >
      <div className="text-xs font-medium uppercase tracking-wide text-muted">{kpi.label}</div>
      <div className="mt-2 text-2xl font-semibold text-foreground">{kpi.display}</div>
      <p className="mt-2 line-clamp-2 text-xs text-muted">{kpi.tooltip}</p>
    </Link>
  );
}
