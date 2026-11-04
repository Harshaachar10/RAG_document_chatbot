import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getApiBaseUrl } from '../api/client';
import { fetchAiJobs } from '../api/ai';
import { fetchActivity, fetchQualitySummary } from '../api/sources';
import { ErrorState } from '../components/ErrorState';
import { FilterBar, FilterField, inputClass } from '../components/FilterBar';
import { Skeleton } from '../components/Skeleton';
import { useUrlState } from '../hooks/useUrlState';
import { formatDateTime } from '../utils/dateUtils';
import { displayValue, percent } from '../utils/formatters';

export function QualityPage() {
  const { get, setMany } = useUrlState();
  const tab = get('tab', 'quality');
  const search = get('search');
  const page = Number(get('page', '1'));

  const jobsQuery = useQuery({
    queryKey: ['ai-jobs'],
    queryFn: ({ signal }) => fetchAiJobs(signal),
  });
  const qualityQuery = useQuery({
    queryKey: ['quality'],
    queryFn: ({ signal }) => fetchQualitySummary(signal),
    enabled: tab === 'quality',
  });
  const activityQuery = useQuery({
    queryKey: ['activity', search, page],
    queryFn: ({ signal }) => fetchActivity({ search, page, page_size: 25 }, signal),
    enabled: tab === 'activity',
  });

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Quality & Activity</h1>
          <p className="mt-1 text-sm text-muted">Data-quality indicators computed from linked records, plus steward activity.</p>
        </div>
        <a
          className="rounded-md border border-border px-3 py-2 text-sm"
          href={`${getApiBaseUrl()}/exports/${tab === 'activity' ? 'activity' : 'source_records'}`}
        >
          Export CSV
        </a>
      </header>

      <div className="flex gap-2">
        <button type="button" className={`rounded-md px-3 py-1.5 text-sm ${tab === 'quality' ? 'bg-primary text-white' : 'bg-slate-100'}`} onClick={() => setMany({ tab: 'quality' })}>Quality</button>
        <button type="button" className={`rounded-md px-3 py-1.5 text-sm ${tab === 'activity' ? 'bg-primary text-white' : 'bg-slate-100'}`} onClick={() => setMany({ tab: 'activity', page: '1' })}>Activity</button>
      </div>

      {tab === 'quality' ? (
        <>
          {qualityQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
          {qualityQuery.isError ? <ErrorState message={(qualityQuery.error as Error).message} onRetry={() => qualityQuery.refetch()} /> : null}
          {qualityQuery.data ? (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-4">
                <Metric label="Unresolved records" value={qualityQuery.data.unresolved_records} href="/sources?status=unresolved" />
                <Metric label="Conflicting cases" value={qualityQuery.data.conflicting_cases} href="/reviews?case_type=identifier_conflict&status=pending" />
                <Metric label="Pending reviews" value={qualityQuery.data.pending_review_volume} href="/reviews?status=pending" />
                <Metric label="Inconsistent evidence refs" value={qualityQuery.data.inconsistent_evidence_refs} />
              </div>
              <p className="rounded-md border border-border bg-white px-3 py-2 text-sm text-muted">
                {qualityQuery.data.matching_accuracy_note}
              </p>
              <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
                <h3 className="text-sm font-semibold">AI analysis execution</h3>
                <div className="mt-3 grid gap-2 text-sm md:grid-cols-4">
                  {Object.entries(qualityQuery.data.ai_job_counts || {}).map(([status, count]) => (
                    <div key={status} className="rounded-md border border-border px-3 py-2">
                      <div className="text-xs uppercase text-muted">{status}</div>
                      <div className="text-lg font-semibold">{count}</div>
                    </div>
                  ))}
                </div>
                {jobsQuery.isError ? <ErrorState message={(jobsQuery.error as Error).message} onRetry={() => jobsQuery.refetch()} /> : null}
                <ul className="mt-3 space-y-1 text-sm">
                  {(jobsQuery.data?.items || []).slice(0, 8).map((job) => (
                    <li key={job.job_id}>
                      {job.operation || 'analysis'} · {job.status}
                      {job.completed_at ? ` · ${formatDateTime(job.completed_at)}` : ''}
                      {job.cached ? ' · Previously generated' : ''}
                    </li>
                  ))}
                </ul>
              </section>
              <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
                <h3 className="text-sm font-semibold">Source completeness</h3>
                <div className="mt-3 overflow-auto">
                  <table className="min-w-full text-sm">
                    <thead className="text-xs uppercase text-muted">
                      <tr>
                        <th className="py-1 text-left">Source</th>
                        <th className="py-1 text-left">Rows</th>
                        <th className="py-1 text-left">Completeness</th>
                      </tr>
                    </thead>
                    <tbody>
                      {qualityQuery.data.source_completeness.map((s) => (
                        <tr key={String(s.source_id)} className="border-t border-border">
                          <td className="py-2">{displayValue(s.source_name)}</td>
                          <td className="py-2">{displayValue(s.row_count)}</td>
                          <td className="py-2">{percent(s.completeness as number)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
              <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
                <h3 className="text-sm font-semibold">Missing fields</h3>
                <ul className="mt-3 space-y-2 text-sm">
                  {qualityQuery.data.missing_fields.map((m) => (
                    <li key={String(m.field)} className="flex justify-between gap-3">
                      <span>{displayValue(m.field)}</span>
                      <span className="text-muted">{displayValue(m.count)} rows</span>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          ) : null}
        </>
      ) : (
        <>
          <FilterBar>
            <FilterField label="Search">
              <input className={inputClass} value={search} onChange={(e) => setMany({ search: e.target.value, page: '1' })} />
            </FilterField>
          </FilterBar>
          {activityQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
          {activityQuery.isError ? <ErrorState message={(activityQuery.error as Error).message} onRetry={() => activityQuery.refetch()} /> : null}
          {activityQuery.data ? (
            <div className="overflow-auto rounded-[12px] border border-border bg-white">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-xs uppercase text-muted">
                  <tr>
                    <th className="px-3 py-2 text-left">Timestamp</th>
                    <th className="px-3 py-2 text-left">Actor</th>
                    <th className="px-3 py-2 text-left">Entity</th>
                    <th className="px-3 py-2 text-left">Action</th>
                    <th className="px-3 py-2 text-left">Reason</th>
                    <th className="px-3 py-2 text-left">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {activityQuery.data.items.map((row) => (
                    <tr key={String(row.audit_id)} className="border-t border-border">
                      <td className="px-3 py-2">{formatDateTime(String(row.occurred_at || ''))}</td>
                      <td className="px-3 py-2">{displayValue(row.actor_label)}</td>
                      <td className="px-3 py-2">
                        {row.doctor_id ? (
                          <Link className="text-primary hover:underline" to={`/golden-records/${String(row.doctor_id)}`}>
                            {displayValue(row.doctor_name || row.doctor_id)}
                          </Link>
                        ) : displayValue(row.entity)}
                      </td>
                      <td className="px-3 py-2">{displayValue(row.action)}</td>
                      <td className="px-3 py-2">{displayValue(row.summary)}</td>
                      <td className="px-3 py-2">
                        {row.is_seeded ? (
                          <span className="text-xs text-muted" title="Seeded historical sample event">Sample history</span>
                        ) : (
                          <span className="text-xs text-emerald-800">Live decision</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

function Metric({ label, value, href }: { label: string; value: number; href?: string }) {
  const body = (
    <div className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
      <div className="text-xs uppercase text-muted">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
  return href ? <Link to={href}>{body}</Link> : body;
}
