import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchProfileSummary } from '../../../api/ai';
import { fetchDoctor, fetchDoctorHistory, fetchDoctorSourceRecords } from '../../../api/doctors';
import type { DoctorSummary, HistoryEvent, SourceRecordItem } from '../../../api/contracts';
import { fetchReviewWorkspace, type ReviewCase } from '../../../api/reviews';
import { ErrorState } from '../../../components/ErrorState';
import { Skeleton } from '../../../components/Skeleton';
import { useShell } from '../../../layouts/shell';

const TABS = [
  ['overview', 'Overview'],
  ['records', 'Records'],
  ['timeline', 'Timeline'],
  ['lineage', 'Lineage'],
  ['impact', 'Prescriber impact'],
  ['payments', 'Payments'],
  ['separate', 'Kept separate'],
  ['history', 'History'],
] as const;

const TAB_ALIAS: Record<string, string> = {
  summary: 'overview',
  known: 'overview',
  linked: 'records',
  changes: 'history',
  similar: 'separate',
  ask: 'overview',
};

const SOURCE_COLOR: Record<string, string> = {
  legacy_master: '#8a9bb0',
  nppes: '#1e5aa8',
  crm: '#0d8065',
  claims: '#1e5aa8',
  events: '#c27a00',
  payments: '#bf3329',
  hub: '#35a98c',
  notes: '#5f6f82',
};

const NPI_LABEL: Record<string, string> = {
  VERIFIED: 'Verified',
  VERIFIED_AFTER_CLEANING: 'Verified',
  INVALID: 'Invalid',
  PLACEHOLDER: 'Placeholder',
  GROUP_NPI: 'Organization NPI',
  DEACTIVATED: 'Deactivated',
  MISMATCH: 'Suspected mismatch',
  MISSING: 'Missing',
};

type Row = {
  id: string;
  source: string;
  sourceKey: string;
  name: string;
  npi: string;
  npiLabel: string;
  practice: string;
  city: string;
  state: string;
  date: string;
  foundBy: string;
  score: number | null;
  pending: boolean;
  amount: number | null;
  round: number | null;
};

export function DoctorProfile({
  doctorId,
  tab = 'overview',
  onTabChange,
}: {
  doctorId: string;
  tab?: string;
  onTabChange?: (tab: string) => void;
}) {
  const shell = useShell();
  const active = TAB_ALIAS[tab] || tab;
  const [lens, setLens] = useState<'golden' | 'raw'>('golden');
  const [field, setField] = useState<string | null>(null);
  const [versions, setVersions] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const doctorQuery = useQuery({ queryKey: ['doctor', doctorId], queryFn: ({ signal }) => fetchDoctor(doctorId, signal) });
  const recordsQuery = useQuery({
    queryKey: ['doctor-records', doctorId],
    queryFn: ({ signal }) => fetchDoctorSourceRecords(doctorId, signal),
  });
  const historyQuery = useQuery({
    queryKey: ['doctor-history', doctorId],
    queryFn: ({ signal }) => fetchDoctorHistory(doctorId, {}, signal),
  });
  const summaryQuery = useQuery({
    queryKey: ['doctor-ai-summary', doctorId],
    queryFn: ({ signal }) => fetchProfileSummary(doctorId, signal),
  });
  const board = useQuery({ queryKey: ['review-workspace'], queryFn: ({ signal }) => fetchReviewWorkspace(signal) });

  const doctor = doctorQuery.data;
  useEffect(() => {
    if (doctor?.preferred_name) shell.setSubtitle(doctor.preferred_name);
  }, [doctor?.preferred_name, shell]);

  const pending = (board.data?.items || []).filter((item) => item.doctor_id === doctorId);
  const rows = useMemo(() => mergeRows(recordsQuery.data?.items || [], pending), [recordsQuery.data, pending]);

  if (doctorQuery.isLoading) return <Skeleton className="h-96 w-full" />;
  if (doctorQuery.isError || !doctor) {
    return <ErrorState message={(doctorQuery.error as Error)?.message || 'Doctor not found'} onRetry={() => doctorQuery.refetch()} />;
  }

  const pct = doctor.completeness ?? 0;
  const missing = doctor.missing_fields || [];
  const practice = String((doctor.primary_affiliation as { organization_name?: string } | null)?.organization_name || '');
  const former = (doctor.former_names || [])[0] || '';
  const initials = doctor.preferred_name
    .split(/\s+/)
    .filter((part) => part && !['MD', 'DO', 'NP', 'Jr', 'Sr'].includes(part.replace('.', '')))
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase();
  const linked = rows.filter((row) => !row.pending);
  const summaryText =
    (summaryQuery.data?.analysis?.response as { summary?: string } | undefined)?.summary || doctor.profile_brief || '';

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <Link className="back" to="/doctors">
        ← All golden records
      </Link>
      <div className="card dhead">
        <div className="avatar" aria-hidden>
          {initials}
        </div>
        <div>
          <h2>
            {doctor.preferred_name}
            {doctor.is_new ? <span className="pill new" style={{ verticalAlign: 'middle', marginLeft: 8 }}>New</span> : null}
          </h2>
          <div className="dmeta">
            <span className="mono">NPI {doctor.official_npi || 'none'}</span>
            {headerStatus(doctor)}
            <span>{doctor.specialty || 'Specialty not recorded'}</span>
            {practice ? <span>{practice}</span> : null}
            <span>{[doctor.city, doctor.state].filter(Boolean).join(', ') || 'Location not recorded'}</span>
          </div>
          {former ? <div className="faint" style={{ fontSize: 13, marginTop: 3 }}>Formerly {former}</div> : null}
        </div>
        <div className="acts" style={{ display: 'flex', gap: 18, alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="ring" title={missing.length ? `Missing: ${missing.join(', ')}` : 'Missing: nothing'}>
            <Ring pct={pct} />
            <div className="lb">
              <b>{pct}%</b>complete
            </div>
          </div>
          {pending.length ? (
            <Link className="link" to={`/review?group=doctor&case=${encodeURIComponent(pending[0].id)}`}>
              {pending.length} decision{pending.length > 1 ? 's' : ''} pending →
            </Link>
          ) : null}
          <button type="button" className="btn" onClick={() => shell.openAsk(doctorId)}>
            Ask
          </button>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div className="seg" role="tablist" aria-label="View">
          <button type="button" className={lens === 'golden' ? 'on' : ''} onClick={() => setLens('golden')}>
            Golden record
          </button>
          <button type="button" className={lens === 'raw' ? 'on' : ''} data-tour="raw-view" onClick={() => setLens('raw')}>
            What your systems show today
          </button>
        </div>
        <span className="muted" style={{ fontSize: 13 }}>
          {lens === 'raw' ? 'The same person, as scattered records before cleanup' : 'One trusted record built from every source'}
        </span>
      </div>

      {lens === 'raw' ? (
        <RawPanel rows={rows} onGolden={() => setLens('golden')} />
      ) : (
        <>
          <div className="ai" data-tour="ai-summary">
            <div className="ai-h">
              <b>AI summary</b>
              <span>Generated from confirmed records</span>
              <button type="button" className="link" style={{ marginLeft: 'auto' }} onClick={() => setVersions((open) => !open)}>
                Previous versions
              </button>
            </div>
            {summaryText ? <p>{summaryText}</p> : <p className="muted">A summary is stored after confirmed records are linked.</p>}
            <p>
              {linked.length} records from {new Set(linked.map((row) => row.sourceKey)).size} sources are linked.
              {pending.length ? ` ${pending.length} item${pending.length > 1 ? 's are' : ' is'} waiting for review.` : ''}
            </p>
            {pending.length ? (
              <div className="pending-note">
                {pending.length} pending item{pending.length > 1 ? 's are' : ' is'} not included until reviewed:{' '}
                {pending.map((item) => (
                  <Link key={item.id} className="cite" to={`/review?case=${encodeURIComponent(item.id)}`}>
                    {item.record_id}
                  </Link>
                ))}
              </div>
            ) : null}
            {versions ? <p className="muted">Only the current summary is stored. It is rewritten when a confirmed link changes.</p> : null}
          </div>
          <div className="card">
            <div className="tabs" role="tablist">
              {TABS.map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  className={`tab ${active === id ? 'on' : ''}`}
                  aria-selected={active === id}
                  data-tour={id === 'separate' ? 'kept-separate' : undefined}
                  onClick={() => onTabChange?.(id)}
                >
                  {id === 'records' ? `Records (${linked.length})` : label}
                </button>
              ))}
            </div>
            <div className="card-b">
              {active === 'overview' ? (
                <Overview doctor={doctor} practice={practice} field={field} onField={setField} onRequest={() => setNote('Request noted for the data owner. Source systems are not written to.')} />
              ) : null}
              {active === 'records' ? <Records rows={linked} pending={pending} /> : null}
              {active === 'timeline' ? <Timeline rows={rows} events={historyQuery.data?.items || []} /> : null}
              {active === 'lineage' ? <Lineage rows={rows} doctor={doctor} practice={practice} /> : null}
              {active === 'impact' ? <Impact rows={rows} name={doctor.preferred_name} /> : null}
              {active === 'payments' ? <Payments rows={rows} /> : null}
              {active === 'separate' ? <KeptSeparate doctorId={doctorId} /> : null}
              {active === 'history' ? <History events={historyQuery.data?.items || []} /> : null}
            </div>
          </div>
        </>
      )}
      {note ? (
        <div className="toast" role="status">
          <span>{note}</span>
          <button type="button" className="iconbtn" aria-label="Dismiss" style={{ color: '#fff' }} onClick={() => setNote(null)}>
            ×
          </button>
        </div>
      ) : null}
    </div>
  );
}

function headerStatus(doctor: DoctorSummary) {
  const status = (doctor.npi_status || '').toLowerCase();
  if (doctor.provisional || !doctor.official_npi) return <span className="pill new">Provisional</span>;
  if (status.includes('deactivat')) return <span className="pill warn">NPI deactivated</span>;
  return <span className="pill ok">Verified</span>;
}

function Ring({ pct }: { pct: number }) {
  const radius = 20;
  const circ = 2 * Math.PI * radius;
  const color = pct >= 85 ? 'var(--ok)' : pct >= 60 ? 'var(--warn)' : 'var(--bad)';
  return (
    <svg viewBox="0 0 48 48" aria-hidden>
      <circle cx="24" cy="24" r={radius} fill="none" stroke="var(--line)" strokeWidth="5" />
      <circle
        cx="24"
        cy="24"
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth="5"
        strokeLinecap="round"
        strokeDasharray={`${(circ * pct) / 100} ${circ}`}
      />
    </svg>
  );
}

function Overview({
  doctor,
  practice,
  field,
  onField,
  onRequest,
}: {
  doctor: DoctorSummary;
  practice: string;
  field: string | null;
  onField: (field: string) => void;
  onRequest: () => void;
}) {
  const former = (doctor.former_names || []).join(', ');
  const phone = formatPhone(doctor.professional_phone);
  const fields: Array<[string, string, string, string]> = [
    ['Legal name', doctor.preferred_name, 'Registry', 'Legal name comes from the registry when an NPI is verified'],
    ['Former names', former, former ? 'Registry · other sources' : '', 'Kept as aliases for search'],
    ['NPI', doctor.official_npi || '', doctor.official_npi ? 'Registry' : '', doctor.official_npi ? 'Active person NPI on the golden record' : 'No person NPI is stored'],
    ['Credential', doctor.credential || doctor.credential_details || '', 'Registry', ''],
    ['Specialty', doctor.specialty || '', 'Registry taxonomy', ''],
    ['Practice', practice, practice ? 'Most recent trusted source' : '', ''],
    ['Location', [doctor.city, doctor.state].filter(Boolean).join(', '), doctor.city ? 'Most recent trusted source' : '', ''],
    ['Phone', phone, phone ? 'Registry' : '', 'A shared clinic line counts as weak evidence'],
    ['Licenses', (doctor.license_states || []).join(', '), doctor.license_states?.length ? 'Registry' : '', ''],
    ['Email', doctor.professional_email || '', doctor.professional_email ? 'Source record' : '', ''],
  ];
  const pct = doctor.completeness ?? 0;
  const missing = doctor.missing_fields || [];
  const known = (doctor.known_values || []).filter((item) => !field || String(item.kind || item.field || '').toLowerCase().includes(field.toLowerCase()));
  return (
    <>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
        <span className={`pill ${pct >= 85 ? 'ok' : 'warn'}`}>{pct}% complete</span>
        <span className="muted">{missing.length ? `Missing: ${missing.join(', ')}` : 'All key fields filled'}</span>
        {missing.length ? (
          <button type="button" className="btn sm" onClick={onRequest}>
            Request missing data
          </button>
        ) : null}
      </div>
      <div className="tw">
        <table>
          <thead>
            <tr>
              <th>Field</th>
              <th>Value</th>
              <th>Source</th>
              <th>How chosen</th>
            </tr>
          </thead>
          <tbody>
            {fields.map(([label, value, source, how]) => (
              <tr key={label} className="click" onClick={() => onField(label)}>
                <td>{label}</td>
                <td>{value ? <b>{value}</b> : <span className="missing">Missing</span>}</td>
                <td className="muted">{source || '—'}</td>
                <td className="muted">{how}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {field ? (
        <div style={{ marginTop: 14 }}>
          <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>Other stored values for {field}</h3>
          {known.length ? (
            <div className="tw">
              <table>
                <thead>
                  <tr>
                    <th>Value</th>
                    <th>Kind</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {known.map((item, index) => (
                    <tr key={`${item.value}-${index}`}>
                      <td>{String(item.value || '')}</td>
                      <td className="muted">{String(item.kind || item.field || '')}</td>
                      <td className="muted">{String(item.source || '')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">No competing value is stored for this field.</p>
          )}
        </div>
      ) : null}
    </>
  );
}

function Records({ rows, pending }: { rows: Row[]; pending: ReviewCase[] }) {
  const groups = new Map<string, Row[]>();
  rows.forEach((row) => {
    const list = groups.get(row.source) || [];
    list.push(row);
    groups.set(row.source, list);
  });
  return (
    <>
      {[...groups.entries()].map(([source, list]) => (
        <div key={source} style={{ marginBottom: 18 }}>
          <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>
            {source} <span className="faint">({list.length})</span>
          </h3>
          <div className="tw">
            <table>
              <thead>
                <tr>
                  <th>Record</th>
                  <th>Name as written</th>
                  <th>Date</th>
                  <th>Found by</th>
                  <th className="n">Score</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {list.map((row) => (
                  <tr key={row.id}>
                    <td className="mono">{row.id}</td>
                    <td>{row.name || '—'}</td>
                    <td className="mono">{row.date || '—'}</td>
                    <td><span className="pill outline">{row.foundBy}</span></td>
                    <td className="n">{row.score != null ? row.score.toFixed(2) : '—'}</td>
                    <td><span className="pill ok">Linked</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
      {pending.length ? (
        <>
          <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>Pending decisions</h3>
          <div className="tw">
            <table>
              <tbody>
                {pending.map((item) => (
                  <tr key={item.id} className="click">
                    <td className="mono">
                      <Link className="link" to={`/review?case=${encodeURIComponent(item.id)}`}>{item.record_id}</Link>
                    </td>
                    <td>{item.source_label}</td>
                    <td>{item.record.name || '—'}</td>
                    <td><span className={`pill ${item.risk_tone}`}>{item.type_label}</span></td>
                    <td className="muted">{item.question}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </>
  );
}

function Timeline({ rows, events }: { rows: Row[]; events: HistoryEvent[] }) {
  const items = [
    ...rows.filter((row) => row.date).map((row) => ({
      date: row.date,
      title: `${row.source} · ${row.id}`,
      sub: `${row.name ? `${row.name} · ` : ''}${row.foundBy}${row.score != null ? ` (${row.score.toFixed(2)})` : ''}`,
      pending: row.pending,
      href: row.pending ? `/review?case=${encodeURIComponent(row.id)}` : undefined,
    })),
    ...events.map((event) => ({
      date: (event.document_date || event.recorded_at || '').slice(0, 10),
      title: event.title,
      sub: event.description || event.activity_label || '',
      pending: false,
      href: undefined as string | undefined,
    })),
  ].filter((item) => item.date).sort((a, b) => b.date.localeCompare(a.date));
  if (!items.length) return <div className="empty"><b>No dated events</b><span>Linked records do not have event dates yet.</span></div>;
  return (
    <div className="timeline">
      {items.map((item) => (
        <div key={`${item.date}-${item.title}`} className={`tl ${item.pending ? 'pending' : ''}`}>
          <span className="d">{item.date}</span>
          <span className="rail"><span className="node" style={{ background: item.pending ? 'var(--warn)' : 'var(--accent)', color: '#fff' }} /></span>
          <span className="body">
            <b>
              {item.href ? <Link className="link" to={item.href}>{item.title}</Link> : item.title}
              {item.pending ? <span className="pill warn">Pending</span> : null}
            </b>
            <span>{item.sub}</span>
          </span>
        </div>
      ))}
    </div>
  );
}

function Lineage({ rows, doctor, practice }: { rows: Row[]; doctor: DoctorSummary; practice: string }) {
  const [filter, setFilter] = useState('all');
  const [open, setOpen] = useState<Set<string>>(new Set());
  const visible = rows.filter((row) => {
    if (filter === 'l1') return row.round === 0 || row.sourceKey === 'nppes' || row.sourceKey === 'legacy_master';
    if (filter === 'l2') return (row.round ?? 0) > 0;
    return true;
  });
  const sources = [...new Set(visible.map((row) => row.sourceKey))];
  const blocks: Array<{ key: string; source: string; rows: Row[]; expanded: boolean }> = sources.map((source) => ({
    key: source,
    source,
    rows: visible.filter((row) => row.sourceKey === source),
    expanded: open.has(source),
  }));
  function toggle(source: string) {
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(source)) next.delete(source);
      else next.add(source);
      return next;
    });
  }
  const decisions = [...new Set(visible.map((row) => (row.pending ? 'Pending review' : row.round === 0 ? 'Verified NPI' : 'Layer 2 match')))];
  return (
    <>
      <div className="chips" style={{ marginBottom: 12 }}>
        {[
          ['all', 'All'],
          ['l1', 'Verified NPI'],
          ['l2', 'Layer 2'],
        ].map(([id, label]) => (
          <button key={id} type="button" className={`chip ${filter === id ? 'on' : ''}`} onClick={() => setFilter(id)}>
            {label}
          </button>
        ))}
        <button type="button" className="chip" onClick={() => setOpen(new Set(sources))}>Expand all</button>
        <button type="button" className="chip" onClick={() => setOpen(new Set())}>Collapse all</button>
        <span className="muted" style={{ marginLeft: 'auto', fontSize: 12.5 }}>Click a source to expand</span>
      </div>
      {blocks.length ? (
        <LineageSvg blocks={blocks} decisions={decisions} doctor={doctor} practice={practice} onToggle={toggle} />
      ) : (
        <div className="empty"><b>No records for this filter</b></div>
      )}
      <div className="chips" style={{ marginTop: 10, fontSize: 12, color: 'var(--muted)' }}>
        <span><span className="dot" style={{ background: 'var(--warn)' }} />Pending review</span>
        <span><span className="dot" style={{ background: 'var(--accent)' }} />Golden record</span>
      </div>
    </>
  );
}

function LineageSvg({
  blocks,
  decisions,
  doctor,
  practice,
  onToggle,
}: {
  blocks: Array<{ key: string; source: string; rows: Row[]; expanded: boolean }>;
  decisions: string[];
  doctor: DoctorSummary;
  practice: string;
  onToggle: (source: string) => void;
}) {
  const rowH = 46;
  const items: Array<{ kind: 'rec' | 'grp'; block: (typeof blocks)[number]; row?: Row }> = [];
  blocks.forEach((block) => {
    if (block.expanded) block.rows.forEach((row) => items.push({ kind: 'rec', block, row }));
    else items.push({ kind: 'grp', block, row: block.rows[0] });
  });
  const height = Math.max(240, items.length * rowH + 40);
  const goldY = height / 2;
  const decY = (index: number) => 40 + ((height - 80) * (index + 0.5)) / Math.max(1, decisions.length);
  return (
    <div className="lineage">
      <svg viewBox={`0 0 960 ${height + 10}`} role="img" aria-label={`Lineage graph for ${doctor.preferred_name}`}>
        {['Source', 'Record', 'Match decision', 'Golden record'].map((label, index) => (
          <text key={label} x={[20, 230, 520, 740][index]} y="16" className="s" style={{ fontSize: 11, letterSpacing: '0.06em', fill: 'var(--muted)' }}>
            {label.toUpperCase()}
          </text>
        ))}
        {blocks.map((block, index) => {
          const y = 40 + index * ((height - 40) / Math.max(1, blocks.length));
          return (
            <g key={block.key} className="nd src" tabIndex={0} role="button" onClick={() => onToggle(block.source)}>
              <rect x="20" y={y - 20} width="170" height="40" rx="8" />
              <text x="32" y={y - 2} fontWeight="600">{block.expanded ? '▾' : '▸'} {block.rows[0]?.source}</text>
              <text x="44" y={y + 14} className="s">{block.rows.length} record{block.rows.length > 1 ? 's' : ''}</text>
            </g>
          );
        })}
        {items.map((item, index) => {
          const y = 40 + index * rowH;
          const label = item.kind === 'rec' ? item.row?.id || '' : `${item.block.rows.length} ${item.block.rows[0]?.source} records`;
          return (
            <g key={`${item.block.key}-${item.row?.id || 'grp'}-${index}`} className={`nd ${item.row?.pending ? 'pend' : ''}`} tabIndex={0} role="button" onClick={() => onToggle(item.block.source)}>
              <rect x="230" y={y} width="230" height="36" rx="7" />
              <text x="240" y={y + 22}>{label}</text>
            </g>
          );
        })}
        {decisions.map((label, index) => (
          <g key={label} className="nd dec">
            <rect x="520" y={decY(index) - 18} width="170" height="36" rx="18" />
            <text x="605" y={decY(index) + 4} textAnchor="middle">{label}</text>
          </g>
        ))}
        <g className="nd gold">
          <rect x="740" y={goldY - 46} width="200" height="92" rx="10" />
          <text x="754" y={goldY - 16} fontWeight="700">{doctor.preferred_name}</text>
          <text x="754" y={goldY + 2} className="s">NPI {doctor.official_npi || 'none'}</text>
          <text x="754" y={goldY + 18} className="s">{practice.slice(0, 30) || 'Practice not recorded'}</text>
          <text x="754" y={goldY + 34} className="s">Golden record</text>
        </g>
      </svg>
    </div>
  );
}

function Impact({ rows, name }: { rows: Row[]; name: string }) {
  const claims = rows.filter((row) => row.sourceKey === 'claims');
  if (!claims.length) return <div className="empty"><b>No claims linked</b><span>This doctor has no claims in the loaded data.</span></div>;
  const groups = new Map<string, number>();
  claims.forEach((row) => {
    const key = row.npiLabel === 'Organization NPI' ? 'Organization NPI (clinic)' : row.npi ? `Stated NPI ${row.npi}` : 'No NPI on the claim';
    groups.set(key, (groups.get(key) || 0) + 1);
  });
  const after = claims.filter((row) => !row.pending).length;
  const pending = claims.length - after;
  const max = Math.max(1, claims.length);
  return (
    <>
      <p className="muted" style={{ margin: '0 0 14px' }}>Before cleanup, claims were grouped by the NPI as received. After cleanup they roll up to one golden record.</p>
      <div className="grid g2">
        <div>
          <h3 style={{ margin: '0 0 10px', fontSize: 14 }}>Before cleanup</h3>
          <div className="bars">
            {[...groups.entries()].map(([label, count]) => (
              <div key={label} className="bar-row">
                <span>{label}</span>
                <div className="b alt" style={{ width: `${(count / max) * 100}%` }} />
                <span className="num">{count}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h3 style={{ margin: '0 0 10px', fontSize: 14 }}>After cleanup</h3>
          <div className="bars">
            <div className="bar-row">
              <span>{name}</span>
              <div className="b after" style={{ width: `${(after / max) * 100}%` }} />
              <span className="num">{after}</span>
            </div>
            {pending ? (
              <div className="bar-row">
                <span>Pending review</span>
                <div className="b alt" style={{ width: `${(pending / max) * 100}%`, opacity: 0.5 }} />
                <span className="num">{pending}</span>
              </div>
            ) : null}
          </div>
          <p style={{ margin: '12px 0 0', fontWeight: 500 }}>
            {groups.size > 1 ? `Previously split across ${groups.size} identities; now one prescriber.` : 'No split found for this doctor.'}
          </p>
        </div>
      </div>
    </>
  );
}

function Payments({ rows }: { rows: Row[] }) {
  const payments = rows.filter((row) => row.sourceKey === 'payments');
  if (!payments.length) return <div className="empty"><b>No payments</b><span>No transfers of value are linked to this doctor.</span></div>;
  const total = payments.reduce((sum, row) => sum + (row.amount || 0), 0);
  return (
    <>
      <div className="tw">
        <table>
          <thead>
            <tr>
              <th>Payment</th>
              <th>Date</th>
              <th className="n">Amount</th>
              <th>Stated NPI</th>
              <th>Open Payments readiness</th>
            </tr>
          </thead>
          <tbody>
            {payments.map((row) => (
              <tr key={row.id}>
                <td className="mono">{row.pending ? <Link className="link" to={`/review?case=${encodeURIComponent(row.id)}`}>{row.id}</Link> : row.id}</td>
                <td className="mono">{row.date || '—'}</td>
                <td className="n">{row.amount != null ? money(row.amount) : '—'}</td>
                <td className="mono">{row.npi || '—'} {row.npiLabel ? <span className="pill neu">{row.npiLabel}</span> : null}</td>
                <td>{row.pending ? <span className="pill bad">Needs compliance review</span> : !row.npi ? <span className="pill warn">Missing NPI</span> : <span className="pill ok">Ready to report</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted" style={{ margin: '10px 0 0' }}>Total {money(total)}. Filed values are never changed automatically.</p>
    </>
  );
}

function KeptSeparate({ doctorId }: { doctorId: string }) {
  const query = useQuery({
    queryKey: ['similar', doctorId],
    queryFn: ({ signal }) =>
      import('../../../api/client').then(({ apiFetch }) =>
        apiFetch<{ doctors: Array<Record<string, unknown>> }>(`/doctors/${doctorId}/similar`, { signal }),
      ),
  });
  if (query.isLoading) return <Skeleton className="h-24 w-full" />;
  const doctors = query.data?.doctors || [];
  if (!doctors.length) return <div className="empty"><b>No similar doctors</b><span>No other doctor came close to this record.</span></div>;
  return (
    <div data-tour="kept-separate" style={{ display: 'grid', gap: 12 }}>
      {doctors.map((other) => (
        <div key={String(other.doctor_id)} className="card" style={{ boxShadow: 'none' }}>
          <div className="card-b" style={{ display: 'grid', gap: 10 }}>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <div>
                <b><Link className="link" to={`/doctors/${other.doctor_id}`}>{String(other.name || '')}</Link></b>
                <div className="muted mono">NPI {String(other.npi || 'none')} · {String(other.location || '')}</div>
              </div>
            </div>
            <div className="reason">
              <h4>Why they were kept separate</h4>
              <ul><li>{String(other.reason || 'A hard stop or a different verified identity kept these doctors apart.')}</li></ul>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function History({ events }: { events: HistoryEvent[] }) {
  if (!events.length) return <div className="empty"><b>No history yet</b><span>Field changes appear here after a confirmed update.</span></div>;
  return (
    <div className="tw">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Field</th>
            <th>Old value</th>
            <th>New value</th>
            <th>Evidence</th>
            <th>Decided by</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.event_id}>
              <td className="mono">{(event.document_date || event.recorded_at || '').slice(0, 10)}</td>
              <td>{event.issue_label || event.event_type}</td>
              <td className="muted">{event.previous_value || '—'}</td>
              <td><b>{event.new_value || event.title}</b></td>
              <td>
                {event.source_record_id ? <span className="cite">{event.source_record_id.split(':').pop()}</span> : '—'}
                {event.evidence_quotation ? <div className="faint" style={{ fontSize: 12 }}>&quot;{event.evidence_quotation}&quot;</div> : null}
              </td>
              <td className="muted">{event.actor || 'Rule'}</td>
              <td><span className="pill ok">{event.review_status || 'Confirmed'}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RawPanel({ rows, onGolden }: { rows: Row[]; onGolden: () => void }) {
  const names = new Set(rows.map((row) => normalize(row.name)).filter(Boolean));
  const npis = new Set(rows.map((row) => row.npi.replace(/\D/g, '')).filter((value) => value.length >= 9));
  const practices = new Set(rows.map((row) => row.practice.toLowerCase()).filter(Boolean));
  const cities = new Set(rows.map((row) => row.city.toLowerCase()).filter(Boolean));
  return (
    <div className="card" id="rawPanel" data-tour="raw-panel">
      <div className="card-b" style={{ display: 'grid', gap: 16 }}>
        <div className="rawstrip">
          <div><b>{rows.length}</b><span>separate records</span></div>
          <div><b>{names.size}</b><span>ways of writing the name</span></div>
          <div><b>{npis.size}</b><span>different NPIs</span></div>
          <div><b>{practices.size}</b><span>practice names</span></div>
          <div><b>{cities.size}</b><span>cities</span></div>
        </div>
        <div className="rawgrid">
          {rows.map((row) => (
            <article key={`${row.sourceKey}-${row.id}`} className="rawcard" style={{ borderTopColor: SOURCE_COLOR[row.sourceKey] || 'var(--line-2)' }}>
              <span className="s"><span>{row.source}</span><span className="mono">{row.id}</span></span>
              <b>{row.name || <i className="faint">no name</i>}</b>
              <span className="r mono">{row.npi ? `NPI ${row.npi}` : 'No NPI'} {row.npiLabel ? <span className="pill neu">{row.npiLabel}</span> : null}</span>
              <span className="r">{row.practice || <i className="faint">no practice</i>}</span>
              <span className="r">{[row.city, row.state].filter(Boolean).join(', ') || <i className="faint">no location</i>}{row.date ? ` · ${row.date}` : ''}</span>
            </article>
          ))}
        </div>
        <div className="banner warn">Without cleanup, these records look like different people. Reports, targeting and payment filings would split or mix them.</div>
        <button type="button" className="btn primary" style={{ justifySelf: 'start' }} onClick={onGolden}>
          See them as one golden record
        </button>
      </div>
    </div>
  );
}

function mergeRows(records: SourceRecordItem[], pending: ReviewCase[]): Row[] {
  const linked: Row[] = records.map((record) => ({
    id: record.display_id || record.source_record_id.split(':').pop() || record.source_record_id,
    source: record.source_name || record.source_id,
    sourceKey: record.source_id,
    name: record.recorded_name || '',
    npi: record.provider_identifier || '',
    npiLabel: NPI_LABEL[(record.npi_status || '').toUpperCase()] || '',
    practice: record.practice_name || '',
    city: record.city || '',
    state: record.state || '',
    date: (record.record_date || '').slice(0, 10),
    foundBy: foundByLabel(record),
    score: typeof record.match_score === 'number' ? record.match_score : null,
    pending: false,
    amount: record.amount_cents != null ? record.amount_cents / 100 : null,
    round: record.match_round ?? null,
  }));
  const seen = new Set(linked.map((row) => row.id));
  pending.forEach((item) => {
    if (seen.has(item.record_id)) return;
    linked.push({
      id: item.record_id,
      source: item.source_label,
      sourceKey: item.source_key || '',
      name: item.record.name || '',
      npi: item.record.npi || '',
      npiLabel: item.record.npi_label || '',
      practice: item.record.practice || '',
      city: item.record.city || '',
      state: item.record.state || '',
      date: (item.record.date || '').slice(0, 10),
      foundBy: 'Pending review',
      score: item.candidates[0]?.score ?? null,
      pending: true,
      amount: item.amount ?? null,
      round: null,
    });
  });
  return linked;
}

function foundByLabel(record: SourceRecordItem) {
  const found = record.found_by || [];
  if (record.match_round === 0) return 'Verified NPI';
  if (record.source_id === 'legacy_master') return 'Legacy master';
  if (found.length) return `Layer 2 · ${found.join(' + ')}`;
  if ((record.match_round ?? 0) > 0) return `Layer 2 · iteration ${record.match_round}`;
  return record.linkage_explanation || 'Linked';
}

function formatPhone(value?: string | null) {
  const digits = (value || '').replace(/\D/g, '');
  if (digits.length === 10) return `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
  return value || '';
}

function money(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
}

function normalize(value: string) {
  return value.toLowerCase().replace(/[^a-z ]/g, '').replace(/\b(dr|md|do|np|phd|jr|sr)\b/g, '').split(/\s+/).filter(Boolean).sort().join(' ');
}
