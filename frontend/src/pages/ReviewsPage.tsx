import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { fetchReviews } from '../api/reviews';
import { fetchReferenceData } from '../api/dashboard';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { FilterBar, FilterField, inputClass } from '../components/FilterBar';
import { TableSkeleton } from '../components/Skeleton';
import { StatusBadge } from '../components/StatusBadge';
import { useUrlState } from '../hooks/useUrlState';
import { displayValue } from '../utils/formatters';

export function ReviewsPage() {
  const navigate = useNavigate();
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
      fetchReviews({ status, case_type: caseType, severity, search, page, page_size: 25, sort_by: 'risk', sort_direction: 'asc' }, signal),
  });

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Review Center</h1>
        <p className="mt-1 text-sm text-muted">
          Each case is a plain-English question. Payment issues sort above routine updates.
        </p>
      </header>

      <div className="flex gap-2" role="tablist" aria-label="Review status">
        {['pending', 'deferred', 'completed', 'approved', 'rejected'].map((s) => (
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
        <FilterField label="Issue type">
          <select className={inputClass} value={caseType} onChange={(e) => setMany({ case_type: e.target.value, page: '1' })}>
            <option value="">All</option>
            {(refQuery.data?.review_case_types || []).map((c) => (
              <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </FilterField>
        <FilterField label="Risk">
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
        <DataTable
          rows={listQuery.data.items}
          rowKey={(r) => r.review_id}
          onRowClick={(r) => navigate(`/reviews/${r.review_id}`)}
          empty={<EmptyState title="No review cases in this view" />}
          columns={[
            {
              key: 'question',
              header: 'Question',
              render: (r) => (
                <div>
                  <div className="font-medium">{displayValue((r as { question?: string }).question || r.title)}</div>
                  <div className="text-xs text-muted">{r.review_id}</div>
                </div>
              ),
            },
            { key: 'source', header: 'Source', render: (r) => displayValue((r as { source_label?: string }).source_label) },
            {
              key: 'doctor',
              header: 'Doctor / candidates',
              render: (r) => displayValue(r.doctor_name || r.candidates_summary, 'No candidates'),
            },
            { key: 'issue', header: 'Issue type', render: (r) => displayValue((r as { issue_type?: string }).issue_type || r.case_type?.replace(/_/g, ' ')) },
            {
              key: 'score',
              header: 'Match score',
              render: (r) => {
                const score = (r as { match_score?: number }).match_score;
                return score == null ? '—' : Number(score).toFixed(3);
              },
            },
            {
              key: 'rec',
              header: 'Recommended action',
              render: (r) => displayValue((r as { recommended_action?: string }).recommended_action)?.replace(/_/g, ' '),
            },
            { key: 'risk', header: 'Risk', render: (r) => <StatusBadge value={r.severity} kind="severity" /> },
            { key: 'age', header: 'Age (days)', render: (r) => r.age_days ?? '—' },
            { key: 'reviewer', header: 'Reviewer', render: (r) => displayValue(r.assigned_reviewer, 'Unassigned') },
            { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} kind="review" /> },
          ]}
        />
      ) : null}
    </div>
  );
}
