import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchDoctors, exportDoctorsUrl } from '../api/doctors';
import type { DoctorListItem } from '../api/contracts';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { TableSkeleton } from '../components/Skeleton';
import { useShell } from '../layouts/shell';
import { useUrlState } from '../hooks/useUrlState';
import { useEffect } from 'react';

const CHIPS = [
  ['all', 'All'],
  ['review', 'Needs review'],
  ['new', 'New evidence'],
  ['provisional', 'Provisional'],
  ['same', 'Same-name doctor'],
  ['incomplete', 'Incomplete'],
  ['changed', 'Changed recently'],
] as const;

function naiveName(row: DoctorListItem) {
  return (row.preferred_name || '')
    .toLowerCase()
    .replace(/[^a-z\s-]/g, ' ')
    .replace(/-/g, ' ')
    .split(/\s+/)
    .filter((token) => token && !['md', 'do', 'np', 'pa', 'phd', 'jr', 'sr', 'dr'].includes(token))
    .slice(0, 3)
    .join(' ');
}

export function GoldenRecordsPage() {
  const { get, setMany } = useUrlState();
  const navigate = useNavigate();
  const shell = useShell();
  const search = get('search');
  const chip = get('chip', 'all');
  const listQuery = useQuery({
    queryKey: ['doctors', search, 'all'],
    queryFn: ({ signal }) =>
      fetchDoctors({ search, page: 1, page_size: 100, sort_by: 'preferred_name', sort_direction: 'asc' }, signal),
  });

  useEffect(() => {
    shell.setSubtitle(listQuery.data ? `${listQuery.data.total} doctors · one record per person` : '');
  }, [listQuery.data, shell]);

  const sameNames = useMemo(() => {
    const groups = new Map<string, number>();
    (listQuery.data?.items || []).forEach((row) => {
      const key = naiveName(row);
      if (key) groups.set(key, (groups.get(key) || 0) + 1);
    });
    return groups;
  }, [listQuery.data]);

  const items = listQuery.data?.items || [];
  const matches = (row: DoctorListItem, id: (typeof CHIPS)[number][0]) => {
    if (id === 'review') return row.pending_item_count > 0;
    if (id === 'new') return Boolean(row.is_new);
    if (id === 'provisional') return Boolean(row.provisional);
    if (id === 'same') return (sameNames.get(naiveName(row)) || 0) > 1;
    if (id === 'incomplete') return (row.completeness || 0) < 100;
    if (id === 'changed') return Boolean(row.is_new);
    return true;
  };
  const rows = items.filter((row) => matches(row, chip as (typeof CHIPS)[number][0]));

  return (
    <>
      <div className="card">
        <div className="card-b" style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <div className="chips">
            {CHIPS.map(([id, label]) => (
              <button key={id} type="button" className={`chip ${chip === id ? 'on' : ''}`} onClick={() => setMany({ chip: id === 'all' ? '' : id })}>
                {label}
                <span className="c">{items.filter((row) => matches(row, id)).length}</span>
              </button>
            ))}
          </div>
          <div style={{ flex: 1 }} />
          <input
            style={{ border: '1px solid var(--line-2)', borderRadius: 8, padding: '8px 12px', minWidth: 200 }}
            placeholder="Filter by name, NPI, practice"
            aria-label="Filter doctors"
            value={search}
            onChange={(event) => setMany({ search: event.target.value })}
          />
          <a className="btn" href={exportDoctorsUrl()}>
            Export CSV
          </a>
          <a className="btn" href={exportDoctorsUrl().replace('/doctors', '/npi_mapping')}>
            Source → NPI mapping
          </a>
        </div>
      </div>
      {listQuery.isLoading ? <TableSkeleton /> : null}
      {listQuery.isError ? <ErrorState message={(listQuery.error as Error).message} onRetry={() => listQuery.refetch()} /> : null}
      {listQuery.data ? (
        <div className="card tw" data-tour="doctors-table">
          <table>
            <thead>
              <tr>
                <th>Doctor</th>
                <th>NPI</th>
                <th>Status</th>
                <th>Specialty</th>
                <th>Practice</th>
                <th>City</th>
                <th className="n">Records</th>
                <th className="n">Sources</th>
                <th>Completeness</th>
                <th className="n">Open issues</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={10}>
                    <EmptyState title="No doctors match" />
                  </td>
                </tr>
              ) : (
                rows.map((row) => {
                  const pct = row.completeness || 0;
                  const color = pct >= 85 ? 'var(--ok)' : pct >= 60 ? 'var(--warn)' : 'var(--bad)';
                  return (
                    <tr key={row.doctor_id} className="click" onClick={() => navigate(`/doctors/${row.doctor_id}`)}>
                      <td>
                        <b>{row.preferred_name}</b>
                        {row.is_new ? <span className="newdot" title="New" /> : null}
                        {row.former_name ? <div className="faint" style={{ fontSize: 12 }}>formerly {row.former_name}</div> : null}
                      </td>
                      <td className="mono">{row.official_npi || <span className="faint">none</span>}</td>
                      <td>
                        {row.provisional ? (
                          <span className="pill new">Provisional</span>
                        ) : row.pending_item_count ? (
                          <span className="pill warn">Needs review</span>
                        ) : (
                          <span className="pill ok">{row.badge || row.npi_status}</span>
                        )}
                      </td>
                      <td>{row.specialty || <span className="faint">not recorded</span>}</td>
                      <td>{row.primary_affiliation || <span className="faint">not recorded</span>}</td>
                      <td>{[row.city, row.state].filter(Boolean).join(', ') || <span className="faint">not recorded</span>}</td>
                      <td className="n">{row.linked_record_count}</td>
                      <td className="n">{row.source_count || 0}</td>
                      <td>
                        <span className="mbar" title={`Missing: ${(row.missing_fields || []).join(', ') || 'nothing'}`}>
                          <span className="tr">
                            <i style={{ width: `${pct}%`, background: color }} />
                          </span>
                          <span className="num">{pct}%</span>
                        </span>
                      </td>
                      <td className="n">{row.pending_item_count ? <span className="pill warn">{row.pending_item_count}</span> : <span className="faint">0</span>}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  );
}
