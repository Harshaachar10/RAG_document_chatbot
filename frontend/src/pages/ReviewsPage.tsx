import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { fetchReviews } from '../api/reviews';
import { fetchReferenceData } from '../api/dashboard';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { FilterBar, FilterField, inputClass } from '../components/FilterBar';
import { TableSkeleton } from '../components/Skeleton';
import { StatusBadge } from '../components/StatusBadge';
import { useUrlState } from '../hooks/useUrlState';

export function ReviewsPage() {
  const { get, setMany } = useUrlState();
  const status = get('status', 'pending');
  const caseType = get('case_type');
  const severity = get('severity');
  const search = get('search');
  const page = Number(get('page', '1'));

  const refQuery = useQuery({ queryKey: ['reference'], queryFn: ({ signal }) => fetchReferenceData(signal) });
  const listQuery = useQuery({
    queryKey: ['reviews', status, caseType, severity, search, page],
    queryFn: ({ signal }) =>
      fetchReviews({ status, case_type: caseType, severity, search, page, page_size: 25 }, signal),
  });

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Review Center</h1>
        <p className="mt-1 text-sm text-muted">Steward decisions for ambiguous matches and proposed field changes.</p>
      </header>

      <div className="flex gap-2" role="tablist" aria-label="Review status">
        {['pending', 'deferred', 'completed'].map((s) => (
          <button
            key={s}
            type="button"
            role="tab"
            aria-selected={status === s}
            className={`rounded-md px-3 py-1.5 text-sm capitalize ${status === s ? 'bg-primary text-white' : 'bg-slate-100'}`}
            onClick={() => setMany({ status: s, page: '1' })}
          >
            {s}
          </button>
        ))}
      </div>

      <FilterBar>
        <FilterField label="Search">
          <input className={inputClass} value={search} onChange={(e) => setMany({ search: e.target.value, page: '1' })} />
        </FilterField>
        <FilterField label="Case type">
          <select className={inputClass} value={caseType} onChange={(e) => setMany({ case_type: e.target.value, page: '1' })}>
            <option value="">All</option>
            {(refQuery.data?.review_case_types || []).map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </FilterField>
        <FilterField label="Severity">
          <select className={inputClass} value={severity} onChange={(e) => setMany({ severity: e.target.value, page: '1' })}>
            <option value="">All</option>
            {(refQuery.data?.severities || []).map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </FilterField>
      </FilterBar>

      {listQuery.isLoading ? <TableSkeleton /> : null}
      {listQuery.isError ? <ErrorState message={(listQuery.error as Error).message} onRetry={() => listQuery.refetch()} /> : null}
      {listQuery.data ? (
        <>
          <DataTable
            rows={listQuery.data.items}
            rowKey={(r) => r.review_id}
            empty={<EmptyState title="No review cases in this view" />}
            columns={[
              { key: 'case', header: 'Case', render: (r) => r.title },
              { key: 'doctor', header: 'Doctor / candidates', render: (r) => r.doctor_name || r.candidates_summary || r.doctor_id || '—' },
              { key: 'type', header: 'Type', render: (r) => r.case_type },
              { key: 'sev', header: 'Severity', render: (r) => <StatusBadge value={r.severity} kind="severity" /> },
              { key: 'age', header: 'Age (days)', render: (r) => r.age_days ?? '—' },
              { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} kind="review" /> },
              {
                key: 'action',
                header: 'Review',
                render: (r) => (
                  <Link className="text-primary hover:underline" to={`/reviews/${r.review_id}`}>
                    Open
                  </Link>
                ),
              },
            ]}
          />
          <div className="flex justify-between text-sm">
            <span className="text-muted">{listQuery.data.total} cases</span>
            <div className="flex gap-2">
              <button type="button" className="rounded-md border px-3 py-1.5" disabled={page <= 1} onClick={() => setMany({ page: String(page - 1) })}>Previous</button>
              <button type="button" className="rounded-md border px-3 py-1.5" disabled={page * 25 >= listQuery.data.total} onClick={() => setMany({ page: String(page + 1) })}>Next</button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
