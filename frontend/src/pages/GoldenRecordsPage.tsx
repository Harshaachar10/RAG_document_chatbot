import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
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
          <h1 className="text-2xl font-semibold">Golden Records</h1>
          <p className="mt-1 text-sm text-muted">
            Clean master profiles resolved to people and NPIs. Total: {listQuery.data?.total ?? '—'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a href={exportDoctorsUrl()} className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-accent">
            Export CSV
          </a>
          <a href={exportDoctorsUrl().replace('/doctors', '/npi_mapping')} className="rounded-md border border-border px-3 py-2 text-sm">
            Source→NPI mapping
          </a>
        </div>
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
              {
                key: 'name',
                header: 'Doctor name',
                render: (r) => (
                  <div>
                    <div className="font-medium">{r.preferred_name}</div>
                    {r.badge ? <span className="mt-1 inline-block rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase">{r.badge}</span> : null}
                  </div>
                ),
              },
              { key: 'npi', header: 'NPI', render: (r) => r.official_npi || '—' },
              { key: 'npi_status', header: 'NPI status', render: (r) => r.npi_status },
              { key: 'id', header: 'Master ID', render: (r) => r.master_id || r.doctor_id },
              { key: 'aliases', header: 'Aliases', render: (r) => (r.alias_count ? `${r.alias_count}` : '—') },
              { key: 'cred', header: 'Credential', render: (r) => r.credential || '—' },
              { key: 'specialty', header: 'Specialty', render: (r) => r.specialty || '—' },
              { key: 'aff', header: 'Current organization', render: (r) => r.primary_affiliation || '—' },
              { key: 'loc', header: 'Location', render: (r) => r.location || [r.city, r.state].filter(Boolean).join(', ') || '—' },
              { key: 'lic', header: 'License states', render: (r) => (r.license_states || []).join(', ') || '—' },
              {
                key: 'linked',
                header: 'Linked records',
                render: (r) => (
                  <button
                    type="button"
                    className="text-primary hover:underline"
                    onClick={(e) => {
                      e.stopPropagation();
                      scrollRef.current = window.scrollY;
                      setMany({ doctor_id: r.doctor_id, tab: 'linked' });
                    }}
                  >
                    {r.linked_record_count}
                  </button>
                ),
              },
              { key: 'sources', header: 'Source count', render: (r) => r.source_count ?? '—' },
              { key: 'issues', header: 'Open issues', render: (r) => r.open_issues ?? r.pending_item_count },
              { key: 'updated', header: 'Last updated', render: (r) => formatDate(r.updated_at) },
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
