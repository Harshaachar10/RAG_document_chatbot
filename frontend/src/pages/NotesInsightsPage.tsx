import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { fetchNotesInsights } from '../api/notes';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { FilterBar, FilterField, inputClass } from '../components/FilterBar';
import { TableSkeleton } from '../components/Skeleton';
import { useUrlState } from '../hooks/useUrlState';
import { displayValue } from '../utils/formatters';

export function NotesInsightsPage() {
  const { get, setMany } = useUrlState();
  const search = get('search');
  const page = Number(get('page', '1'));
  const query = useQuery({
    queryKey: ['notes-insights', search, page],
    queryFn: ({ signal }) => fetchNotesInsights({ search, page, page_size: 25 }, signal),
  });

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Notes Insights</h1>
        <p className="mt-1 text-sm text-muted">
          Redacted call notes and inquiries. Adverse-event flags are never silently removed.
        </p>
      </header>
      <FilterBar>
        <FilterField label="Search">
          <input className={inputClass} value={search} onChange={(e) => setMany({ search: e.target.value, page: '1' })} />
        </FilterField>
      </FilterBar>
      {query.isLoading ? <TableSkeleton /> : null}
      {query.isError ? <ErrorState message={(query.error as Error).message} onRetry={() => query.refetch()} /> : null}
      {query.data ? (
        <DataTable
          rows={query.data.items}
          rowKey={(r) => String(r.note_id)}
          empty={<EmptyState title="No notes insights" />}
          columns={[
            {
              key: 'note',
              header: 'Redacted note',
              render: (r) => <div className="max-w-md whitespace-pre-wrap text-sm">{displayValue(r.redacted_note)}</div>,
            },
            { key: 'mention', header: 'Doctor mention', render: (r) => displayValue(r.doctor_mention, '—') },
            {
              key: 'resolved',
              header: 'Resolved doctor',
              render: (r) =>
                r.resolved_doctor_id ? (
                  <Link className="text-primary hover:underline" to={`/golden-records?doctor_id=${r.resolved_doctor_id}`}>
                    {displayValue(r.resolved_doctor_name)}
                  </Link>
                ) : (
                  '—'
                ),
            },
            { key: 'change', header: 'Proposed change', render: (r) => displayValue(r.proposed_change, '—') },
            { key: 'quote', header: 'Quoted sentence', render: (r) => displayValue(r.quoted_sentence) },
            { key: 'status', header: 'Review status', render: (r) => displayValue(r.review_status) },
            {
              key: 'ae',
              header: 'Adverse-event flags',
              render: (r) => {
                const flags = (r.adverse_event_flags as string[]) || [];
                return flags.length ? flags.join(', ') : 'None';
              },
            },
          ]}
        />
      ) : null}
    </div>
  );
}
