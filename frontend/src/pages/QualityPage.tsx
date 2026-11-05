import { useQuery } from '@tanstack/react-query';
import { getApiBaseUrl } from '../api/client';
import { fetchActivity, fetchQualitySummary } from '../api/sources';
import { ErrorState } from '../components/ErrorState';
import { FilterBar, FilterField, inputClass } from '../components/FilterBar';
import { Skeleton } from '../components/Skeleton';
import { useUrlState } from '../hooks/useUrlState';
import { formatDateTime } from '../utils/dateUtils';
import { displayValue } from '../utils/formatters';

export function QualityPage() {
  const { get, setMany } = useUrlState();
  const tab = get('tab', 'audit');
  const search = get('search');
  const page = Number(get('page', '1'));

  const qualityQuery = useQuery({
    queryKey: ['quality'],
    queryFn: ({ signal }) => fetchQualitySummary(signal),
    enabled: tab === 'audit' || tab === 'quality',
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
          <h1 className="text-2xl font-semibold">Quality & Audit</h1>
          <p className="mt-1 text-sm text-muted">
            Audit trail, pipeline runs, and upload history. Synthetic data only.
          </p>
        </div>
        <a className="rounded-md border border-border px-3 py-2 text-sm" href={`${getApiBaseUrl()}/exports/activity`}>
          Export CSV
        </a>
      </header>

      <div className="flex gap-2">
        <button type="button" className={`rounded-md px-3 py-1.5 text-sm ${tab === 'audit' ? 'bg-primary text-white' : 'bg-slate-100'}`} onClick={() => setMany({ tab: 'audit' })}>Audit</button>
        <button type="button" className={`rounded-md px-3 py-1.5 text-sm ${tab === 'activity' ? 'bg-primary text-white' : 'bg-slate-100'}`} onClick={() => setMany({ tab: 'activity', page: '1' })}>Activity</button>
      </div>

      {tab === 'audit' ? (
        <>
          {qualityQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
          {qualityQuery.isError ? <ErrorState message={(qualityQuery.error as Error).message} onRetry={() => qualityQuery.refetch()} /> : null}
          {qualityQuery.data ? (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-4">
                <Metric label="Unresolved records" value={qualityQuery.data.unresolved_records} />
                <Metric label="Conflicting cases" value={qualityQuery.data.conflicting_cases} />
                <Metric label="Pending reviews" value={qualityQuery.data.pending_review_volume} />
                <Metric label="Inconsistent evidence refs" value={qualityQuery.data.inconsistent_evidence_refs} />
              </div>
              <p className="rounded-md border border-border bg-white px-3 py-2 text-sm text-muted">
                {qualityQuery.data.matching_accuracy_note}
              </p>
              <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
                <h3 className="text-sm font-semibold">Recent audit events</h3>
                <ul className="mt-3 space-y-2 text-sm">
                  {((qualityQuery.data as { audit_events?: Array<Record<string, unknown>> }).audit_events || []).map((a) => (
                    <li key={String(a.audit_id)} className="border-t border-border pt-2 first:border-0 first:pt-0">
                      <div className="font-medium">{displayValue(a.action)} · {displayValue(a.actor_label || a.actor, 'System')}</div>
                      <div className="text-xs text-muted">{formatDateTime(String(a.occurred_at || a.created_at || ''))} · {displayValue(a.summary || a.detail)}</div>
                    </li>
                  ))}
                  {!((qualityQuery.data as { audit_events?: unknown[] }).audit_events || []).length ? (
                    <li className="text-muted">No audit events yet</li>
                  ) : null}
                </ul>
              </section>
              <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
                <h3 className="text-sm font-semibold">Pipeline / upload runs</h3>
                <ul className="mt-3 space-y-2 text-sm">
                  {[
                    ...(((qualityQuery.data as { pipeline_runs?: Array<Record<string, unknown>> }).pipeline_runs) || []),
                    ...(((qualityQuery.data as { upload_batches?: Array<Record<string, unknown>> }).upload_batches) || []),
                  ].slice(0, 20).map((run, idx) => (
                    <li key={idx} className="border-t border-border pt-2 first:border-0 first:pt-0">
                      <div className="font-medium">{displayValue(run.run_id || run.batch_id)} · {displayValue(run.status)}</div>
                      <div className="text-xs text-muted">{formatDateTime(String(run.updated_at || run.created_at || ''))}</div>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          ) : null}
        </>
      ) : null}

      {tab === 'activity' ? (
        <>
          <FilterBar>
            <FilterField label="Search">
              <input className={inputClass} value={search} onChange={(e) => setMany({ search: e.target.value, page: '1' })} />
            </FilterField>
          </FilterBar>
          {activityQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
          {activityQuery.isError ? <ErrorState message={(activityQuery.error as Error).message} onRetry={() => activityQuery.refetch()} /> : null}
          {activityQuery.data ? (
            <ul className="space-y-2 rounded-[12px] border border-border bg-white p-4 text-sm shadow-sm">
              {(activityQuery.data.items || []).map((item: Record<string, unknown>) => (
                <li key={String(item.audit_id || item.event_id)} className="border-t border-border pt-2 first:border-0 first:pt-0">
                  <div className="font-medium">{displayValue(item.summary || item.title || item.action)}</div>
                  <div className="text-xs text-muted">{formatDateTime(String(item.occurred_at || item.recorded_at || ''))}</div>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
      <div className="text-xs uppercase text-muted">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}
