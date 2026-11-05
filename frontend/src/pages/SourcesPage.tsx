import { useQuery } from '@tanstack/react-query';
import { fetchSourceRecords, fetchSources } from '../api/sources';
import { ErrorState } from '../components/ErrorState';
import { FilterBar, FilterField, inputClass } from '../components/FilterBar';
import { Skeleton } from '../components/Skeleton';
import { SourceRecordsTable } from '../features/sources/components/SourceRecordsTable';
import { useUrlState } from '../hooks/useUrlState';
import { displayValue } from '../utils/formatters';

function n(value: unknown) {
  return String(Number(value || 0));
}

export function SourcesPage() {
  const { get, setMany } = useUrlState();
  const sourceId = get('source_id');
  const status = get('status');
  const search = get('search');
  const page = Number(get('page', '1'));

  const sourcesQuery = useQuery({
    queryKey: ['sources'],
    queryFn: ({ signal }) => fetchSources(signal),
  });
  const selected = sourceId || sourcesQuery.data?.items[0]?.source_id || '';
  const recordsQuery = useQuery({
    queryKey: ['source-records', selected, status, search, page],
    queryFn: ({ signal }) =>
      fetchSourceRecords(selected, { status, search, page, page_size: 25 }, signal),
    enabled: !!selected,
  });

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Data Sources</h1>
        <p className="mt-1 text-sm text-muted">
          Eight historical sources feeding the identity pipeline. Metrics link to matching records.
        </p>
      </header>

      {sourcesQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
      {sourcesQuery.isError ? <ErrorState message={(sourcesQuery.error as Error).message} onRetry={() => sourcesQuery.refetch()} /> : null}
      {sourcesQuery.data ? (
        <div className="overflow-auto rounded-[12px] border border-border bg-white shadow-sm">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-muted">
              <tr>
                <th className="px-3 py-2 text-left">Source</th>
                <th className="px-3 py-2 text-right">Rows</th>
                <th className="px-3 py-2 text-right">NPI present</th>
                <th className="px-3 py-2 text-right">Valid NPI</th>
                <th className="px-3 py-2 text-right">Missing</th>
                <th className="px-3 py-2 text-right">Wrong</th>
                <th className="px-3 py-2 text-right">Group</th>
                <th className="px-3 py-2 text-right">Deactivated</th>
                <th className="px-3 py-2 text-right">Duplicates</th>
                <th className="px-3 py-2 text-right">Resolved</th>
                <th className="px-3 py-2 text-right">In review</th>
                <th className="px-3 py-2 text-right">Unmatched</th>
                <th className="px-3 py-2 text-left">Latest valid date</th>
              </tr>
            </thead>
            <tbody>
              {sourcesQuery.data.items.map((s) => {
                const row = s as unknown as Record<string, unknown>;
                const links = (row.metric_links || {}) as Record<string, string>;
                const Metric = ({ href, value }: { href?: string; value: unknown }) =>
                  href ? (
                    <button type="button" className="text-primary hover:underline" onClick={() => setMany({ source_id: String(s.source_id), page: '1', status: href.includes('unresolved') ? 'unresolved' : href.includes('linked') ? 'linked' : '' })}>
                      {n(value)}
                    </button>
                  ) : (
                    <>{n(value)}</>
                  );
                return (
                  <tr
                    key={s.source_id}
                    className={`border-t border-border ${selected === s.source_id ? 'bg-slate-50' : ''}`}
                  >
                    <td className="px-3 py-2">
                      <button type="button" className="font-medium text-left hover:underline" onClick={() => setMany({ source_id: s.source_id, page: '1' })}>
                        {displayValue(s.source_name)}
                      </button>
                    </td>
                    <td className="px-3 py-2 text-right"><Metric href={links.rows} value={row.row_count} /></td>
                    <td className="px-3 py-2 text-right">{n(row.npi_present)}</td>
                    <td className="px-3 py-2 text-right">{n(row.npi_valid)}</td>
                    <td className="px-3 py-2 text-right"><Metric href={links.npi_missing} value={row.npi_missing} /></td>
                    <td className="px-3 py-2 text-right">{n(row.npi_wrong)}</td>
                    <td className="px-3 py-2 text-right">{n(row.npi_group)}</td>
                    <td className="px-3 py-2 text-right">{n(row.npi_deactivated)}</td>
                    <td className="px-3 py-2 text-right">{n(row.duplicates)}</td>
                    <td className="px-3 py-2 text-right"><Metric href={links.resolved} value={row.resolved} /></td>
                    <td className="px-3 py-2 text-right"><Metric href={links.in_review} value={row.in_review} /></td>
                    <td className="px-3 py-2 text-right"><Metric href={links.unmatched} value={row.unmatched} /></td>
                    <td className="px-3 py-2">{displayValue(row.latest_valid_date)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      <FilterBar>
        <FilterField label="Search">
          <input className={inputClass} value={search} onChange={(e) => setMany({ search: e.target.value, page: '1' })} />
        </FilterField>
        <FilterField label="Status">
          <select className={inputClass} value={status} onChange={(e) => setMany({ status: e.target.value, page: '1' })}>
            <option value="">All</option>
            <option value="linked">Resolved</option>
            <option value="pending_review">In review</option>
            <option value="unresolved">Unmatched</option>
          </select>
        </FilterField>
      </FilterBar>

      {recordsQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
      {recordsQuery.isError ? <ErrorState message={(recordsQuery.error as Error).message} onRetry={() => recordsQuery.refetch()} /> : null}
      {recordsQuery.data ? (
        <SourceRecordsTable rows={recordsQuery.data.items as Array<Record<string, unknown>>} />
      ) : null}
    </div>
  );
}
