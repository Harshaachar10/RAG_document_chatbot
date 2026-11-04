import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { fetchDashboardSummary, fetchReferenceData, fetchSourceBreakdown } from '../api/dashboard';
import { ChartCard } from '../components/ChartCard';
import { ErrorState } from '../components/ErrorState';
import { FilterBar, FilterField, inputClass } from '../components/FilterBar';
import { KpiCard } from '../components/KpiCard';
import { Skeleton } from '../components/Skeleton';
import { StatusBadge } from '../components/StatusBadge';
import { useUrlState } from '../hooks/useUrlState';
import { formatDate, formatDateTime } from '../utils/dateUtils';
import { displayValue } from '../utils/formatters';

export function OverviewPage() {
  const { get, setMany } = useUrlState();
  const sourceId = get('source_id');
  const specialty = get('specialty');
  const state = get('state');
  const reviewState = get('review_state');

  const filters = { source_id: sourceId, specialty, state, review_state: reviewState };
  const refQuery = useQuery({ queryKey: ['reference'], queryFn: ({ signal }) => fetchReferenceData(signal) });
  const summaryQuery = useQuery({
    queryKey: ['dashboard-summary', filters],
    queryFn: ({ signal }) => fetchDashboardSummary(filters, signal),
  });
  const breakdownQuery = useQuery({
    queryKey: ['source-breakdown', sourceId, specialty, state],
    queryFn: ({ signal }) => fetchSourceBreakdown({ source_id: sourceId, specialty, state }, signal),
  });

  const chartData = (breakdownQuery.data?.rows || []).map((row) => {
    const entry: Record<string, string | number> = { source: row.source_name };
    row.segments.forEach((s) => {
      entry[s.status] = s.count;
    });
    return entry;
  });

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Doctor Identity Overview</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Multiple source records may refer to the same doctor, while same-name doctors can remain separate.
            Golden profiles consolidate trusted current information with full evidence history.
          </p>
          <p className="mt-2 text-xs text-muted">
            Synthetic dataset · {formatDateTime(summaryQuery.data?.dataset_updated_at)}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-md border border-border px-3 py-2 text-sm"
            onClick={() => {
              summaryQuery.refetch();
              breakdownQuery.refetch();
            }}
          >
            Refresh
          </button>
          <Link to="/golden-records" className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-accent">
            View Golden Records
          </Link>
        </div>
      </header>

      <FilterBar>
        <FilterField label="Source">
          <select className={inputClass} value={sourceId} onChange={(e) => setMany({ source_id: e.target.value })}>
            <option value="">All sources</option>
            {(refQuery.data?.sources || []).map((s) => (
              <option key={s.source_id} value={s.source_id}>{s.source_name}</option>
            ))}
          </select>
        </FilterField>
        <FilterField label="Specialty">
          <select className={inputClass} value={specialty} onChange={(e) => setMany({ specialty: e.target.value })}>
            <option value="">All</option>
            {(refQuery.data?.specialties || []).map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </FilterField>
        <FilterField label="State">
          <select className={inputClass} value={state} onChange={(e) => setMany({ state: e.target.value })}>
            <option value="">All</option>
            {(refQuery.data?.states || []).map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </FilterField>
        <FilterField label="Review state">
          <select className={inputClass} value={reviewState} onChange={(e) => setMany({ review_state: e.target.value })}>
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="deferred">Deferred</option>
          </select>
        </FilterField>
      </FilterBar>

      {summaryQuery.isLoading ? <Skeleton className="h-28 w-full" /> : null}
      {summaryQuery.isError ? (
        <ErrorState message={(summaryQuery.error as Error).message} onRetry={() => summaryQuery.refetch()} />
      ) : null}

      {summaryQuery.data ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {summaryQuery.data.kpis.map((kpi) => (
            <KpiCard key={kpi.key} kpi={kpi} />
          ))}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard
          title="Resolution by Source"
          summary={breakdownQuery.data?.text_summary || 'Linked, review required, unresolved, and identifier conflict counts by source.'}
        >
          <div className="h-72" role="img" aria-label={breakdownQuery.data?.text_summary || 'Source resolution chart'}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout="vertical" margin={{ left: 24, right: 12 }}>
                <XAxis type="number" />
                <YAxis type="category" dataKey="source" width={120} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar
                  dataKey="linked"
                  stackId="a"
                  fill="#0f766e"
                  name="Linked"
                  cursor="pointer"
                  onClick={(data) => {
                    const row = data as { source?: string };
                    const match = breakdownQuery.data?.rows.find((r) => r.source_name === row.source);
                    if (match) setMany({ source_id: match.source_id });
                    window.location.assign(`/sources?source_id=${match?.source_id || ''}&status=linked`);
                  }}
                />
                <Bar dataKey="review_required" stackId="a" fill="#b45309" name="Review required" />
                <Bar dataKey="unresolved" stackId="a" fill="#c2410c" name="Unresolved" />
                <Bar dataKey="identifier_conflict" stackId="a" fill="#be123c" name="Identifier conflict" />
                <Bar dataKey="duplicate_ingestion" stackId="a" fill="#7c3aed" name="Duplicate ingestion" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold">Priority Review</h3>
          <div className="mt-3 overflow-auto">
            <table className="min-w-full text-sm">
              <thead className="text-xs uppercase text-muted">
                <tr>
                  <th className="py-1 text-left">Case</th>
                  <th className="py-1 text-left">Doctor</th>
                  <th className="py-1 text-left">Severity</th>
                  <th className="py-1 text-left">Action</th>
                </tr>
              </thead>
              <tbody>
                {(summaryQuery.data?.priority_reviews || []).map((row) => (
                  <tr key={String(row.review_id)} className="border-t border-border">
                    <td className="py-2">{displayValue(row.title)}</td>
                    <td className="py-2">{displayValue(row.doctor_name || row.doctor_id)}</td>
                    <td className="py-2"><StatusBadge value={String(row.severity || '')} kind="severity" /></td>
                    <td className="py-2">
                      <Link className="text-primary hover:underline" to={`/reviews/${String(row.review_id)}`}>Review</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold">Recent Doctor Changes</h3>
          <ul className="mt-3 space-y-2 text-sm">
            {(summaryQuery.data?.recent_changes || []).map((c) => (
              <li key={String(c.event_id)}>
                <Link
                  className="font-medium text-primary hover:underline"
                  to={`/golden-records?doctor_id=${String(c.doctor_id)}&tab=history`}
                >
                  {displayValue(c.doctor_name)}
                </Link>
                <div className="text-muted">
                  {displayValue(c.previous_value, '—')} → {displayValue(c.new_value, '—')} · {formatDate(String(c.date || ''))}
                </div>
              </li>
            ))}
          </ul>
        </section>
        <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold">Source Coverage</h3>
          <ul className="mt-3 space-y-2 text-sm">
            {(summaryQuery.data?.source_coverage || []).map((s) => (
              <li key={String(s.source_id)} className="flex items-center justify-between gap-2">
                <div>
                  <div className="font-medium">{displayValue(s.source_name)}</div>
                  <div className="text-xs text-muted">{displayValue(s.row_count)} rows · {formatDate(String(s.latest_data_date || ''))}</div>
                </div>
                <Link className="text-primary hover:underline" to={`/sources?source_id=${String(s.source_id)}`}>View</Link>
              </li>
            ))}
          </ul>
        </section>
        <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold">Recent Decisions</h3>
          <ul className="mt-3 space-y-2 text-sm">
            {(summaryQuery.data?.recent_decisions || []).map((d) => (
              <li key={String(d.audit_id)}>
                <div className="font-medium">{displayValue(d.actor_label)} · {displayValue(d.action)}</div>
                <div className="text-muted">{displayValue(d.doctor_name)} · {formatDateTime(String(d.occurred_at || ''))}</div>
                {d.review_id ? (
                  <Link className="text-primary hover:underline" to={`/reviews/${String(d.review_id)}`}>Detail</Link>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
