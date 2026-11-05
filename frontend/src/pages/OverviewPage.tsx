import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
import { startDemoRun } from '../api/sources';
import { ChartCard } from '../components/ChartCard';
import { ErrorState } from '../components/ErrorState';
import { FilterBar, FilterField, inputClass } from '../components/FilterBar';
import { KpiCard } from '../components/KpiCard';
import { Skeleton } from '../components/Skeleton';
import { useUrlState } from '../hooks/useUrlState';
import { formatDateTime } from '../utils/dateUtils';
import { displayValue } from '../utils/formatters';

export function OverviewPage() {
  const queryClient = useQueryClient();
  const { get, setMany } = useUrlState();
  const sourceId = get('source_id');
  const specialty = get('specialty');
  const state = get('state');
  const view = get('view', 'historical');

  const filters = { source_id: sourceId, specialty, state, view };
  const refQuery = useQuery({ queryKey: ['reference'], queryFn: ({ signal }) => fetchReferenceData(signal) });
  const summaryQuery = useQuery({
    queryKey: ['dashboard-summary', filters],
    queryFn: ({ signal }) => fetchDashboardSummary(filters, signal),
  });
  const breakdownQuery = useQuery({
    queryKey: ['source-breakdown', sourceId, specialty, state],
    queryFn: ({ signal }) => fetchSourceBreakdown({ source_id: sourceId, specialty, state }, signal),
  });
  const runMutation = useMutation({
    mutationFn: () => startDemoRun(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      await queryClient.invalidateQueries({ queryKey: ['source-breakdown'] });
      await queryClient.invalidateQueries({ queryKey: ['doctors'] });
      await queryClient.invalidateQueries({ queryKey: ['reviews'] });
      await queryClient.invalidateQueries({ queryKey: ['sources'] });
    },
  });

  const chartData = (breakdownQuery.data?.rows || []).map((row) => {
    const entry: Record<string, string | number> = { source: row.source_name };
    row.segments.forEach((s) => {
      entry[s.status] = s.count;
    });
    return entry;
  });
  const legend = breakdownQuery.data?.legend || [
    { key: 'AUTO_LINK', label: 'Auto linked' },
    { key: 'REVIEW', label: 'Review' },
    { key: 'COMPLIANCE_REVIEW', label: 'Compliance' },
  ];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Overview</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Resolve every doctor record to the right person and NPI. Clean historical data, then match new uploads against the master.
          </p>
          <p className="mt-2 text-xs text-muted">
            Synthetic data · Last run: {formatDateTime(summaryQuery.data?.last_simulated_run_at || summaryQuery.data?.dataset_updated_at)}
            {summaryQuery.data?.last_run_status ? ` · ${summaryQuery.data.last_run_status}` : ''}
          </p>
        </div>
        <button
          type="button"
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          disabled={runMutation.isPending}
          onClick={() => runMutation.mutate()}
        >
          {runMutation.isPending ? 'Running…' : 'Run historical cleanup'}
        </button>
      </header>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Data view">
        {[
          { id: 'historical', label: 'Historical cleanup' },
          { id: 'incoming', label: 'Incoming records' },
          { id: 'all', label: 'All' },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={view === tab.id}
            className={`rounded-md px-3 py-1.5 text-sm ${view === tab.id ? 'bg-primary text-white' : 'bg-slate-100'}`}
            onClick={() => setMany({ view: tab.id })}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <FilterBar>
        <FilterField label="Source">
          <select className={inputClass} value={sourceId} onChange={(e) => setMany({ source_id: e.target.value })}>
            <option value="">All</option>
            {(refQuery.data?.sources || []).map((s) => (
              <option key={s.source_id} value={s.source_id}>{s.source_name}</option>
            ))}
          </select>
        </FilterField>
        <FilterField label="Specialty">
          <select className={inputClass} value={specialty} onChange={(e) => setMany({ specialty: e.target.value })}>
            <option value="">All</option>
            {(refQuery.data?.specialties || []).map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </FilterField>
        <FilterField label="State">
          <select className={inputClass} value={state} onChange={(e) => setMany({ state: e.target.value })}>
            <option value="">All</option>
            {(refQuery.data?.states || []).map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </FilterField>
      </FilterBar>

      {summaryQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
      {summaryQuery.isError ? <ErrorState message={(summaryQuery.error as Error).message} onRetry={() => summaryQuery.refetch()} /> : null}
      {summaryQuery.data ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {summaryQuery.data.kpis.map((kpi) => (
            <KpiCard key={kpi.key} kpi={kpi} />
          ))}
        </div>
      ) : null}

      {summaryQuery.data?.scorecard_available ? (
        <p className="text-sm text-muted">Synthetic scorecard metrics are available for this dataset.</p>
      ) : null}

      <ChartCard title="Final action by source" summary="Accessible stacked counts of pipeline outcomes per source.">
        {breakdownQuery.isLoading ? <Skeleton className="h-64 w-full" /> : null}
        {breakdownQuery.data ? (
          <div className="h-72 w-full" role="img" aria-label={breakdownQuery.data.text_summary}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                <XAxis dataKey="source" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={60} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Legend />
                {legend.map((item, idx) => (
                  <Bar
                    key={item.key}
                    dataKey={item.key}
                    name={item.label}
                    stackId="a"
                    fill={['#0f766e', '#0369a1', '#b45309', '#7c3aed', '#be123c', '#334155'][idx % 6]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : null}
      </ChartCard>

      <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold">Priority issues</h2>
        <p className="mt-1 text-xs text-muted">Sorted by business risk. Payment compliance ranks above routine updates.</p>
        <div className="mt-3 overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="text-xs uppercase text-muted">
              <tr>
                <th className="px-2 py-1 text-left">Doctor</th>
                <th className="px-2 py-1 text-left">Issue</th>
                <th className="px-2 py-1 text-left">Reason</th>
                <th className="px-2 py-1 text-left">Source</th>
                <th className="px-2 py-1 text-left">Link</th>
              </tr>
            </thead>
            <tbody>
              {(summaryQuery.data?.priority_reviews || []).map((row) => (
                <tr key={String(row.review_id)} className="border-t border-border">
                  <td className="px-2 py-2 font-medium">{displayValue(row.doctor_name)}</td>
                  <td className="px-2 py-2">{displayValue(row.issue || row.title)}</td>
                  <td className="px-2 py-2 text-muted">{displayValue(row.reason)}</td>
                  <td className="px-2 py-2">{displayValue(row.source)}</td>
                  <td className="px-2 py-2">
                    <Link className="text-primary hover:underline" to={String(row.href || `/reviews/${row.review_id}`)}>
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
              {!summaryQuery.data?.priority_reviews?.length ? (
                <tr><td className="px-2 py-3 text-muted" colSpan={5}>No open priority issues</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
