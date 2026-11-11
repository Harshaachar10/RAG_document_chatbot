import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { fetchDashboardSummary } from '../api/dashboard';
import { startDemoRun } from '../api/sources';
import { Dialog } from '../components/Dialog';
import { ErrorState } from '../components/ErrorState';
import { ProcessingDialog } from '../components/ProcessingDialog';
import { type FlowItem } from '../components/ResolutionFlow';
import { Skeleton } from '../components/Skeleton';
import { useShell } from '../layouts/shell';
import { UploadMatchPage } from './UploadMatchPage';

type StoryItem = FlowItem & { npi_status?: string; action?: string };
type SourceCell = { count: number; items?: StoryItem[] };
type SourceRow = {
  source: string;
  total: number;
  items?: StoryItem[];
  linked: SourceCell;
  review: SourceCell;
  compliance: SourceCell;
  unmatched: SourceCell;
  not_a_person: SourceCell;
};
type Cards = {
  doctors?: number;
  rows?: number;
  verified?: number;
  provisional?: number;
  npi_issues?: { invalid?: number; placeholder?: number; group?: number; deactivated?: number; mismatch?: number };
  npi_issue_total?: number;
  payments_at_risk?: { count: number; amount: number; items?: StoryItem[] };
  masters_fixed?: { merges: number; splits: number; new: number; total: number };
  completeness?: { average: number; top_gap: string; top_gap_count: number };
};
type Impact = {
  payment_amount?: number;
  payment_count?: number;
  payment_items?: StoryItem[];
  claims_problem?: number;
  claims_fixed?: number;
  claims_review?: number;
  claims_items?: StoryItem[];
  false_merge_pairs?: number;
  pairs?: Array<{ name: string; doctors: Array<{ name?: string; href: string }> }>;
};

const SOURCE_LABELS: Record<string, string> = {
  nppes: 'NPPES reference',
  legacy_master: 'Legacy master',
  crm: 'CRM',
  claims: 'Claims',
  events: 'Events',
  payments: 'Payments',
  hub: 'Hub enrollments',
  notes: 'Call notes',
};

function sourceLabel(key: string) {
  return SOURCE_LABELS[key] || key.replaceAll('_', ' ');
}

function money(value: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: Number.isInteger(value) ? 0 : 2,
  }).format(value || 0);
}

export function OverviewPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const shell = useShell();
  const [params] = useSearchParams();
  const summaryQuery = useQuery({
    queryKey: ['dashboard-summary', 'historical'],
    queryFn: ({ signal }) => fetchDashboardSummary({ view: 'historical' }, signal),
  });
  const [runId, setRunId] = useState<string | null>(null);
  const [minimized, setMinimized] = useState(false);
  const [deltas, setDeltas] = useState<Record<string, number>>({});
  const [records, setRecords] = useState<{ title: string; items: StoryItem[] } | null>(null);
  const [uploadOpen, setUploadOpen] = useState(params.get('upload') === '1');
  const [uploadMode, setUploadMode] = useState<'historical' | 'new'>('new');
  const [pairsOpen, setPairsOpen] = useState(false);

  const data = summaryQuery.data;
  const story = (data?.story || {}) as {
    needs_run?: boolean;
    loaded_sources?: Array<{ source: string; label?: string; rows?: number }>;
    cards?: Cards;
    impact?: Impact;
    by_source?: SourceRow[];
    conflicts?: { npi_conflicts?: StoryItem[]; same_name_pairs?: Impact['pairs'] };
    alerts?: Array<{ record_id?: string; title?: string; kind?: string; suggested_action?: string; href?: string; quote?: string }>;
    source_quality?: Array<{ source: string; total: number; present_pct?: number; valid_pct?: number; verified_npi: number }>;
  };
  const cards = story.cards;
  const needsRun = story.needs_run || !cards;

  useEffect(() => {
    if (!data) return;
    const when = data.last_simulated_run_at || data.dataset_updated_at;
    shell.setSubtitle(
      needsRun
        ? 'Historical data loaded · not processed yet'
        : `Last run ${when ? new Date(when).toLocaleString() : ''} · ${data.last_run_status || 'completed'}`,
    );
  }, [data, needsRun, shell]);

  useEffect(() => {
    if (params.get('upload') === '1') setUploadOpen(true);
  }, [params]);

  const runMutation = useMutation({
    mutationFn: () => startDemoRun(),
    onSuccess: (run) => {
      const baseline = {
        doctors: cards?.doctors || 0,
        verified: cards?.verified || 0,
        issues: cards?.npi_issue_total || 0,
        payments: cards?.payments_at_risk?.count || 0,
      };
      sessionStorage.setItem('dashboard-baseline', JSON.stringify(baseline));
      setRunId(run.run_id);
      setMinimized(false);
    },
  });
  useEffect(() => {
    const raw = sessionStorage.getItem('dashboard-baseline');
    if (!raw || !cards) return;
    const baseline = JSON.parse(raw) as Record<string, number>;
    const next: Record<string, number> = {};
    (['doctors', 'verified', 'issues', 'payments'] as const).forEach((key) => {
      const value = key === 'issues' ? cards.npi_issue_total || 0 : key === 'payments' ? cards.payments_at_risk?.count || 0 : cards[key] || 0;
      if (typeof baseline[key] === 'number' && value !== baseline[key]) next[key] = value - baseline[key];
    });
    setDeltas(next);
  }, [data?.snapshot_version, cards]);

  function openItems(title: string, items: StoryItem[] | undefined) {
    setRecords({ title, items: items || [] });
  }

  if (summaryQuery.isLoading) {
    return (
      <div className="card">
        <div className="card-b">
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    );
  }
  if (summaryQuery.isError) {
    return <ErrorState message={(summaryQuery.error as Error).message} onRetry={() => summaryQuery.refetch()} />;
  }

  const issues = cards?.npi_issues || {};
  const impact = story.impact || {};
  const sources = story.loaded_sources?.length ? story.loaded_sources : (data?.source_coverage as Array<{ source_id?: string; source_name?: string; row_count?: number }> | undefined)?.map((row) => ({
    source: row.source_id || '',
    label: row.source_name,
    rows: row.row_count,
  }));

  return (
    <>
      {needsRun ? (
        <>
          <div className="hero">
            <div>
              <h2>Historical data is ready to clean</h2>
              <p>
                {(sources || []).length} sources and {(sources || []).reduce((sum, row) => sum + (row.rows || 0), 0)} rows are loaded.
                Running cleanup checks every NPI, builds golden doctor records from verified NPIs, then finds the remaining records.
              </p>
            </div>
            <div className="chips">
              <button type="button" className="btn primary" onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
                Run historical cleanup
              </button>
              <button type="button" className="btn" data-tour="upload" style={{ background: 'transparent', color: '#fff', borderColor: '#6c8fbf' }} onClick={() => setUploadOpen(true)}>
                Upload
              </button>
            </div>
          </div>
          <div className="card">
            <div className="card-h">
              <h2>Loaded sources</h2>
              <span className="hint">Raw data before cleanup</span>
            </div>
            <div className="card-b">
              <div className="srcs">
                {(sources || []).map((row) => (
                  <div key={row.source} className="src">
                    <b>{row.label || sourceLabel(row.source)}</b>
                    <div className="rows num">{row.rows || 0}</div>
                    <span className="muted">rows</span>
                    <span className="pill neu" style={{ justifySelf: 'start' }}>
                      Not checked yet
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="card">
            <div className="empty">
              <b>No golden records yet</b>
              <span>Run historical cleanup to build one record per doctor.</span>
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="chips" style={{ justifyContent: 'flex-end', marginTop: -6 }}>
            <button type="button" className="btn" data-tour="upload" onClick={() => setUploadOpen(true)}>
              Upload
            </button>
            <button type="button" className="btn primary" disabled={runMutation.isPending} onClick={() => runMutation.mutate()}>
              Run historical cleanup
            </button>
          </div>
          <div className="kpis" data-tour="kpis">
            <button type="button" className="kpi" onClick={() => navigate('/doctors')}>
              {deltas.doctors ? <span className="delta">+{deltas.doctors}</span> : null}
              <span className="lbl">Unique doctors</span>
              <span className="val">
                {cards?.doctors} <small>from {cards?.rows} rows</small>
              </span>
              <span className="sub">One golden record per real person</span>
            </button>
            <button type="button" className="kpi" onClick={() => navigate('/doctors?chip=provisional')}>
              {deltas.verified ? <span className="delta">+{deltas.verified}</span> : null}
              <span className="lbl">Doctors with verified NPI</span>
              <span className="val">
                {cards?.verified} <small>of {cards?.doctors}</small>
              </span>
              <div className="bar">
                <i style={{ width: `${cards?.doctors ? ((cards.verified || 0) / cards.doctors) * 100 : 0}%` }} />
              </div>
              <span className="sub">{cards?.provisional} provisional: no NPI on the golden record</span>
            </button>
            <button type="button" className="kpi" onClick={() => openItems('NPI issues found', story.conflicts?.npi_conflicts)}>
              {deltas.issues ? <span className="delta">{deltas.issues}</span> : null}
              <span className="lbl">NPI issues found</span>
              <span className="val">{cards?.npi_issue_total || 0}</span>
              <span className="sub">
                {issues.invalid || 0} invalid · {issues.placeholder || 0} placeholder · {issues.group || 0} organization · {issues.deactivated || 0} deactivated · {issues.mismatch || 0} suspected mismatch
              </span>
            </button>
            <button type="button" className="kpi" onClick={() => openItems('Payments at risk', cards?.payments_at_risk?.items)}>
              {deltas.payments ? <span className="delta down">{deltas.payments}</span> : null}
              <span className="lbl">Payments at risk</span>
              <span className="val">{money(cards?.payments_at_risk?.amount || 0)}</span>
              <span className="sub">{cards?.payments_at_risk?.count || 0} payments need a compliance decision</span>
            </button>
            <button type="button" className="kpi" onClick={() => navigate('/doctors')}>
              <span className="lbl">Master records fixed</span>
              <span className="val">{cards?.masters_fixed?.total || 0}</span>
              <span className="sub">
                {cards?.masters_fixed?.merges || 0} duplicates merged · {cards?.masters_fixed?.splits || 0} blended record split · {cards?.masters_fixed?.new || 0} missing doctors added
              </span>
            </button>
            <button type="button" className="kpi" onClick={() => navigate('/doctors?chip=incomplete')}>
              <span className="lbl">Golden record completeness</span>
              <span className="val">
                {cards?.completeness?.average || 0}
                <small>% average</small>
              </span>
              <div className="bar">
                <i style={{ width: `${cards?.completeness?.average || 0}%`, background: 'var(--warn)' }} />
              </div>
              <span className="sub">
                Most common gap: {(cards?.completeness?.top_gap || 'none').toLowerCase()} ({cards?.completeness?.top_gap_count || 0} doctors)
              </span>
            </button>
          </div>
          <div className="card" id="impactCard" data-tour="impact">
            <div className="card-h">
              <h2>What would have gone wrong without this</h2>
              <span className="hint">Calculated from this run</span>
            </div>
            <div className="card-b">
              <div className="impact">
                <button type="button" className="tile" onClick={() => openItems('Payment reporting', impact.payment_items)}>
                  <span className="k" style={{ color: 'var(--bad)' }}>Payment reporting</span>
                  <b>{money(impact.payment_amount || 0)}</b>
                  <p>in {impact.payment_count || 0} payments would have been reported against the wrong doctor or without a valid NPI.</p>
                </button>
                <button type="button" className="tile" onClick={() => openItems('Claims with a problem NPI', impact.claims_items)}>
                  <span className="k" style={{ color: 'var(--warn)' }}>Prescriber credit</span>
                  <b>{impact.claims_problem || 0} claims</b>
                  <p>
                    had an organization, invalid, or mismatched prescriber NPI. {impact.claims_fixed || 0} are now credited to a doctor; {impact.claims_review || 0} {impact.claims_review === 1 ? 'is' : 'are'} still open.
                  </p>
                </button>
                <button type="button" className="tile" onClick={() => setPairsOpen(true)}>
                  <span className="k" style={{ color: 'var(--accent)' }}>False merges avoided</span>
                  <b>{impact.false_merge_pairs || 0} pairs</b>
                  <p>of different doctors share a name an exact-name match would have merged.</p>
                </button>
              </div>
            </div>
          </div>
          <div className="grid g2">
            <div className="card">
              <div className="card-h">
                <h2>Unresolved by source</h2>
                <span className="hint">Click a number to open those records</span>
              </div>
              <div className="card-b tw">
                <table>
                  <thead>
                    <tr>
                      <th>Source</th>
                      <th className="n">Records</th>
                      <th className="n">Linked</th>
                      <th className="n">Identity</th>
                      <th className="n">Compliance</th>
                      <th className="n">Unmatched</th>
                      <th className="n">Not a person</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(story.by_source || []).map((row) => {
                      const cell = (label: string, cellData: SourceCell | { count: number; items?: StoryItem[] }) => (
                        <td className="n" key={label}>
                          <button
                            type="button"
                            className={`cellbtn ${cellData.count ? '' : 'zero'}`}
                            onClick={() => cellData.count && openItems(`${sourceLabel(row.source)} · ${label}`, cellData.items)}
                          >
                            {cellData.count}
                          </button>
                        </td>
                      );
                      return (
                        <tr key={row.source}>
                          <td>
                            <b>{sourceLabel(row.source)}</b>
                          </td>
                          {cell('all', { count: row.total, items: row.items })}
                          {cell('linked', row.linked)}
                          {cell('identity', row.review)}
                          {cell('compliance', row.compliance)}
                          {cell('unmatched', row.unmatched)}
                          {cell('not a person', row.not_a_person)}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="card">
              <div className="card-h">
                <h2>Conflicts</h2>
                <span className="hint">NPIs that disagree with the record</span>
                <button type="button" className="link right" onClick={() => navigate('/review')}>
                  Open review
                </button>
              </div>
              <div className="card-b">
                <div className="list">
                  {(story.conflicts?.npi_conflicts || []).slice(0, 6).map((row) => (
                    <button key={row.record_id} type="button" className="li" onClick={() => row.href && navigate(row.href)}>
                      <div className="ic bad">!</div>
                      <div className="tx">
                        <b>{row.label || row.record_id}</b>
                        <span>
                          {sourceLabel(row.source || '')} · <span className="mono">{row.record_id}</span>
                        </span>
                      </div>
                    </button>
                  ))}
                  {(story.conflicts?.npi_conflicts || []).length === 0 ? <p className="muted">No NPI conflicts in this run.</p> : null}
                </div>
              </div>
            </div>
          </div>
          <div className="grid g2">
            <div className="card">
              <div className="card-h">
                <h2>Change alerts</h2>
                <span className="hint">Who should act</span>
              </div>
              <div className="card-b">
                <div className="list">
                  {(story.alerts || []).length === 0 ? <p className="muted">No proposed changes in this run.</p> : null}
                  {(story.alerts || []).slice(0, 8).map((alert) => (
                    <button key={`${alert.record_id}-${alert.kind}`} type="button" className="li" onClick={() => navigate(alert.href || '/review')}>
                      <div className={`ic ${alert.kind === 'retirement' || alert.kind === 'deactivated_npi' ? 'bad' : 'new'}`}>→</div>
                      <div className="tx">
                        <b>{alert.title || alert.record_id}</b>
                        <span>{alert.suggested_action}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="card">
              <div className="card-h">
                <h2>Source quality</h2>
                <span className="hint">NPI present vs valid, by source</span>
              </div>
              <div className="card-b">
                {(story.source_quality || []).map((row) => (
                  <button key={row.source} type="button" className="qbar" style={{ width: '100%', background: 'none', border: 0, textAlign: 'left' }} onClick={() => openItems(sourceLabel(row.source), story.by_source?.find((item) => item.source === row.source)?.items)}>
                    <span>{sourceLabel(row.source)}</span>
                    <span className="track">
                      <i className="present" style={{ width: `${row.present_pct || 0}%` }} />
                      <i className="valid" style={{ width: `${row.valid_pct || 0}%` }} />
                    </span>
                    <span className="num muted" style={{ textAlign: 'right' }}>
                      {row.valid_pct || 0}%
                    </span>
                  </button>
                ))}
                <div className="chips" style={{ marginTop: 8, fontSize: 12, color: 'var(--muted)' }}>
                  <span>
                    <span className="dot" style={{ background: 'var(--accent)' }} />
                    Valid NPI
                  </span>
                  <span>
                    <span className="dot" style={{ background: 'var(--accent-line)' }} />
                    NPI present
                  </span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      <ProcessingDialog
        runId={runId}
        minimized={minimized}
        onMinimized={setMinimized}
        onClose={() => {
          setRunId(null);
          void queryClient.invalidateQueries();
        }}
      />

      {records ? (
        <>
          <div className="dscrim" onClick={() => setRecords(null)} />
          <aside className="drawer wide" role="dialog" aria-modal="true" aria-label={records.title}>
            <div className="drawer-h">
              <h2>{records.title}</h2>
              <button type="button" className="iconbtn x" aria-label="Close" onClick={() => setRecords(null)}>
                ×
              </button>
            </div>
            <div className="drawer-b">
              <p className="muted" style={{ margin: 0 }}>
                {records.items.length} records.
              </p>
              <div className="tw card">
                <table>
                  <thead>
                    <tr>
                      <th>Record</th>
                      <th>Name</th>
                      <th>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.items.length === 0 ? (
                      <tr>
                        <td colSpan={3} className="muted">
                          No records in this group.
                        </td>
                      </tr>
                    ) : (
                      records.items.map((item) => (
                        <tr key={`${item.record_id}-${item.href}`} className="click" onClick={() => item.href && navigate(item.href)}>
                          <td className="mono">{item.record_id}</td>
                          <td>{item.label}</td>
                          <td>{item.amount ? money(item.amount) : ''}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </aside>
        </>
      ) : null}

      <Dialog open={pairsOpen} onOpenChange={setPairsOpen} title="False merges avoided">
        <ul className="list">
          {(impact.pairs || []).map((pair) => (
            <li key={pair.name} className="li">
              <div className="tx">
                <b>{pair.name}</b>
                <span>
                  {pair.doctors.map((doctor, index) => (
                    <span key={doctor.href}>
                      {index ? ' · ' : ''}
                      <Link to={doctor.href}>{doctor.name}</Link>
                    </span>
                  ))}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </Dialog>

      <Dialog open={uploadOpen} onOpenChange={setUploadOpen} title="Upload" description="Choose how this file should be used." size="spacious">
        <div className="modes" role="radiogroup" aria-label="Upload mode">
          {([
            ['historical', 'Historical batch', 'Adds files to the historical sources and reruns cleanup from a clean state.'],
            ['new', 'New records', 'Match a CSV, spreadsheet, or document against the golden records.'],
          ] as const).map(([id, label, detail]) => (
            <button key={id} type="button" className={`mode ${uploadMode === id ? 'on' : ''}`} onClick={() => setUploadMode(id)}>
              <b>{label}</b>
              <span>{detail}</span>
            </button>
          ))}
        </div>
        {uploadMode === 'historical' ? (
          <div className="card-b">
            <button
              type="button"
              className="btn primary"
              onClick={() => {
                setUploadOpen(false);
                runMutation.mutate();
              }}
            >
              Rerun historical cleanup
            </button>
          </div>
        ) : (
          <UploadMatchPage />
        )}
      </Dialog>
    </>
  );
}
