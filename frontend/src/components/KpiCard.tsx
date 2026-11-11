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
  const parts = (kpi.parts || []).filter((p) => p.value > 0);

  return (
    <Link
      to={buildHref(kpi)}
      className="block rounded-[12px] border border-border bg-white p-4 shadow-sm transition hover:border-accent hover:shadow"
      title={kpi.tooltip}
    >
      <div className="text-xs font-medium uppercase tracking-wide text-muted">{kpi.label}</div>
      <div className="mt-2 text-2xl font-semibold tabular-nums text-foreground">{kpi.display}</div>
      {kpi.detail ? <p className="mt-1.5 text-xs font-medium text-slate-600">{kpi.detail}</p> : null}
      {parts.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {parts.map((part) => (
            <span
              key={part.label}
              className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700"
            >
              <span className="font-semibold tabular-nums">{part.value}</span>
              <span>{part.label}</span>
            </span>
          ))}
        </div>
      ) : null}
      <p className="mt-2 line-clamp-2 text-xs text-muted">{kpi.tooltip}</p>
    </Link>
  );
}
