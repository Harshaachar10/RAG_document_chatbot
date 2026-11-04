import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchDoctors, exportDoctorsUrl } from '../api/doctors';
import { fetchReferenceData } from '../api/dashboard';
import type { DoctorListItem } from '../api/contracts';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { FilterBar, FilterField, inputClass } from '../components/FilterBar';
import { TableSkeleton } from '../components/Skeleton';
import { DoctorDrawer } from '../features/doctors/components/DoctorDrawer';
import { useUrlState } from '../hooks/useUrlState';
import { formatDate } from '../utils/dateUtils';

export function GoldenRecordsPage() {
  const { get, setMany } = useUrlState();
  const navigate = useNavigate();
  const scrollRef = useRef<number>(0);
  const doctorId = get('doctor_id');
  const tab = get('tab', 'summary');
  const search = get('search');
  const specialty = get('specialty');
  const state = get('state');
  const sourceId = get('source_id');
  const pending = get('pending_review');
  const page = Number(get('page', '1'));
  const pageSize = Number(get('page_size', '25'));
  const [dense, setDense] = useState(false);

  const refQuery = useQuery({ queryKey: ['reference'], queryFn: ({ signal }) => fetchReferenceData(signal) });
  const listQuery = useQuery({
    queryKey: ['doctors', search, specialty, state, sourceId, pending, page, pageSize],
    queryFn: ({ signal }) =>
      fetchDoctors(
        {
          search,
          specialty,
          state,
          source_id: sourceId,
          pending_review: pending === '' ? undefined : pending === 'true',
          page,
          page_size: pageSize,
          sort_by: 'preferred_name',
          sort_direction: 'asc',
        },
        signal,
      ),
  });

  useEffect(() => {
    if (!doctorId && scrollRef.current) {
      window.scrollTo(0, scrollRef.current);
    }
  }, [doctorId]);

  const openDoctor = (row: DoctorListItem) => {
    scrollRef.current = window.scrollY;
    setMany({ doctor_id: row.doctor_id, tab: 'summary' });
  };

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Golden Doctor Records</h1>
          <p className="mt-1 text-sm text-muted">
            Trusted profiles consolidating linked identity evidence. Total profiles: {listQuery.data?.total ?? '—'}
          </p>
        </div>
        <a
          href={exportDoctorsUrl()}
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-accent"
        >
          Export CSV
        </a>
      </header>

      <FilterBar>
        <FilterField label="Search">
          <input
            className={inputClass}
            value={search}
            placeholder="Name, alias, or HCP ID"
            onChange={(e) => setMany({ search: e.target.value, page: '1' })}
          />
        </FilterField>
        <FilterField label="Specialty">
          <select className={inputClass} value={specialty} onChange={(e) => setMany({ specialty: e.target.value, page: '1' })}>
            <option value="">All</option>
            {(refQuery.data?.specialties || []).map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </FilterField>
        <FilterField label="State">
          <select className={inputClass} value={state} onChange={(e) => setMany({ state: e.target.value, page: '1' })}>
            <option value="">All</option>
            {(refQuery.data?.states || []).map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </FilterField>
        <FilterField label="Source">
          <select className={inputClass} value={sourceId} onChange={(e) => setMany({ source_id: e.target.value, page: '1' })}>
            <option value="">All</option>
            {(refQuery.data?.sources || []).map((s) => (
              <option key={s.source_id} value={s.source_id}>{s.source_name}</option>
            ))}
          </select>
        </FilterField>
        <FilterField label="Pending review">
          <select className={inputClass} value={pending} onChange={(e) => setMany({ pending_review: e.target.value, page: '1' })}>
            <option value="">All</option>
            <option value="true">Pending only</option>
            <option value="false">No pending</option>
          </select>
        </FilterField>
        <button type="button" className="rounded-md border border-border px-3 py-2 text-sm" onClick={() => setDense((d) => !d)}>
          Density: {dense ? 'Compact' : 'Comfortable'}
        </button>
      </FilterBar>

      {listQuery.isLoading ? <TableSkeleton /> : null}
      {listQuery.isError ? (
        <ErrorState message={(listQuery.error as Error).message} onRetry={() => listQuery.refetch()} />
      ) : null}
      {listQuery.data ? (
        <>
          <DataTable
            dense={dense}
            rows={listQuery.data.items}
            rowKey={(r) => r.doctor_id}
            onRowClick={openDoctor}
            empty={<EmptyState title="No doctors match these filters" description="Try clearing search or filters." />}
            columns={[
              { key: 'name', header: 'Doctor name', render: (r) => <span className="font-medium">{r.preferred_name}</span> },
              { key: 'id', header: 'Master ID', render: (r) => r.doctor_id },
              { key: 'specialty', header: 'Specialty', render: (r) => r.specialty || '—' },
              {
                key: 'aff',
                header: 'Current affiliation',
                render: (r) => (
                  <span>
                    {r.primary_affiliation || '—'}
                    {r.affiliation_count > 1 ? (
                      <button
                        type="button"
                        className="ml-2 text-xs text-primary hover:underline"
                        onClick={(e) => {
                          e.stopPropagation();
                          setMany({ doctor_id: r.doctor_id, tab: 'summary' });
                        }}
                      >
                        +{r.affiliation_count - 1}
                      </button>
                    ) : null}
                  </span>
                ),
              },
              { key: 'loc', header: 'Location', render: (r) => [r.city, r.state].filter(Boolean).join(', ') || '—' },
              { key: 'linked', header: 'Linked records', render: (r) => r.linked_record_count },
              { key: 'pending', header: 'Pending items', render: (r) => r.pending_item_count },
              { key: 'updated', header: 'Updated', render: (r) => formatDate(r.updated_at) },
              {
                key: 'open',
                header: 'Open',
                render: (r) => (
                  <button
                    type="button"
                    className="text-primary hover:underline"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/golden-records/${r.doctor_id}`);
                    }}
                  >
                    Open
                  </button>
                ),
              },
            ]}
          />
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted">
              Page {listQuery.data.page} of {Math.max(1, Math.ceil(listQuery.data.total / listQuery.data.page_size))} · {listQuery.data.total} total
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40"
                disabled={page <= 1}
                onClick={() => setMany({ page: String(page - 1) })}
              >
                Previous
              </button>
              <button
                type="button"
                className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40"
                disabled={page * pageSize >= listQuery.data.total}
                onClick={() => setMany({ page: String(page + 1) })}
              >
                Next
              </button>
            </div>
          </div>
        </>
      ) : null}

      <DoctorDrawer
        doctorId={doctorId || null}
        open={!!doctorId}
        onOpenChange={(open) => {
          if (!open) setMany({ doctor_id: null, tab: null });
        }}
        tab={tab}
        onTabChange={(next) => setMany({ tab: next })}
      />
    </div>
  );
}
