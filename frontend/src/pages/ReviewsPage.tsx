import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { apiFetch } from '../api/client';
import {
  fetchReviewWorkspace,
  resolveBoardItem,
  submitDecision,
  type ReviewCase,
} from '../api/reviews';
import { ErrorState } from '../components/ErrorState';
import { useShell } from '../layouts/shell';

const FILTERS = [
  ['all', 'All'],
  ['compliance', 'Compliance'],
  ['safety', 'Safety'],
  ['identity', 'Identity'],
  ['proposed', 'Proposed changes'],
  ['unmatched', 'Unmatched'],
] as const;

const FIELDS = ['Name', 'Suffix', 'NPI', 'Specialty', 'Practice', 'Location', 'Phone'] as const;

type PreviewRow = {
  doctor_id?: string;
  name?: string;
  city?: string;
  state?: string;
  specialty?: string;
  score?: number;
  reasons?: string[];
};

function money(value?: number | null) {
  if (value == null || Number.isNaN(value)) return '';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
}

function scoreColor(score?: number | null) {
  if (score == null) return 'var(--neu)';
  if (score >= 0.8) return 'var(--ok)';
  if (score >= 0.5) return 'var(--warn)';
  return 'var(--neu)';
}

function symClass(symbol: string) {
  if (symbol === '✓') return 'y';
  if (symbol === '≈') return 'p';
  if (symbol === '✗') return 'n';
  return 'm';
}

function npiTone(label?: string | null) {
  if (!label) return 'neu';
  if (label === 'Verified') return 'ok';
  if (label === 'Invalid' || label === 'Organization NPI' || label === 'Deactivated' || label === 'Suspected mismatch') return 'bad';
  return 'warn';
}

function location(city?: string | null, state?: string | null) {
  return [city, state].filter(Boolean).join(', ');
}

function recordValue(item: ReviewCase, field: string) {
  const record = item.record;
  if (field === 'Name') return record.name || '';
  if (field === 'NPI') return record.npi || '';
  if (field === 'Specialty') return record.specialty || '';
  if (field === 'Practice') return record.practice || '';
  if (field === 'Location') return location(record.city, record.state);
  return '';
}

function doctorValue(candidate: ReviewCase['candidates'][number], field: string) {
  if (field === 'Name') {
    const former = candidate.former ? ` (formerly ${candidate.former})` : '';
    return `${candidate.name || ''}${former}`;
  }
  if (field === 'Suffix') return candidate.suffix || '';
  if (field === 'NPI') return candidate.npi || '';
  if (field === 'Specialty') return candidate.specialty || '';
  if (field === 'Practice') return candidate.practice || '';
  if (field === 'Location') return location(candidate.city, candidate.state);
  if (field === 'Phone') return candidate.phone || '';
  return '';
}

function newIdempotencyKey() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `idem-${Date.now()}`;
}

export function ReviewsPage() {
  const shell = useShell();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const filter = params.get('filter') || 'all';
  const group = params.get('group') === 'doctor' ? 'doctor' : 'issue';
  const selectedId = params.get('case');
  const board = useQuery({ queryKey: ['review-workspace'], queryFn: ({ signal }) => fetchReviewWorkspace(signal) });
  const [threshold, setThreshold] = useState(0.95);
  const [simOpen, setSimOpen] = useState(false);
  const simulator = useQuery({
    queryKey: ['threshold', threshold],
    queryFn: ({ signal }) => apiFetch<Record<string, unknown>>(`/quality/threshold-simulator?threshold=${threshold}`, { signal }),
  });
  const [tryText, setTryText] = useState('');
  const [tryResult, setTryResult] = useState<PreviewRow[] | null>(null);
  const [tryError, setTryError] = useState<string | null>(null);
  const [trying, setTrying] = useState(false);
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const [previewDoctor, setPreviewDoctor] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState(false);
  const [toast, setToast] = useState<{ text: string; href?: string; label?: string } | null>(null);
  const [leaving, setLeaving] = useState<string | null>(null);

  useEffect(() => {
    shell.setSubtitle(board.data?.subtitle || 'Payments and safety first');
  }, [board.data?.subtitle, shell]);

  const items = board.data?.items || [];
  const counts = board.data?.counts || {};
  const visible = items.filter((item) => filter === 'all' || item.queue_type === filter);
  const selected = visible.find((item) => item.id === selectedId) || visible[0] || null;

  useEffect(() => {
    if (!selected) return;
    if (selectedId !== selected.id) {
      setParams((current) => {
        const next = new URLSearchParams(current);
        next.set('case', selected.id);
        return next;
      }, { replace: true });
    }
  }, [selected, selectedId, setParams]);

  useEffect(() => {
    setPreviewDoctor(null);
    setReason('');
    setReasonError(false);
    const recommended = selected?.candidates.find((row) => row.recommended);
    setCandidateId(recommended?.doctor_id || selected?.candidates[0]?.doctor_id || null);
  }, [selected?.id]);

  const groups = useMemo(() => {
    const names = new Map<string, number>();
    visible.forEach((item) => {
      const name = item.doctor_name || '';
      if (name) names.set(name, (names.get(name) || 0) + 1);
    });
    const buckets = new Map<string, ReviewCase[]>();
    visible.forEach((item) => {
      let key = item.type_label;
      if (group === 'doctor') {
        if (!item.doctor_name || item.queue_type === 'unmatched') key = 'No likely doctor';
        else key = (names.get(item.doctor_name) || 0) > 1 && item.doctor_city ? `${item.doctor_name} · ${item.doctor_city}` : item.doctor_name;
      }
      const list = buckets.get(key) || [];
      list.push(item);
      buckets.set(key, list);
    });
    return [...buckets.entries()].sort((a, b) => {
      if (group !== 'doctor') return 0;
      if (a[0] === 'No likely doctor') return 1;
      if (b[0] === 'No likely doctor') return -1;
      return b[1].length - a[1].length;
    });
  }, [visible, group]);

  function choose(id: string) {
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.set('case', id);
      return next;
    });
  }

  async function tryRecord() {
    const text = tryText.trim() || 'Dr. S Lee, LCI Oncology, Chicago';
    setTryText(text);
    setTrying(true);
    setTryError(null);
    setTryResult(null);
    try {
      const body = await apiFetch<{ candidates?: PreviewRow[] }>('/match/preview', {
        method: 'POST',
        body: JSON.stringify({ text }),
      });
      setTryResult(body.candidates || []);
    } catch (err) {
      setTryError(err instanceof Error ? err.message : 'Preview failed');
    } finally {
      setTrying(false);
    }
  }

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['review-workspace'] });
    await queryClient.invalidateQueries({ queryKey: ['doctors'] });
    await queryClient.invalidateQueries({ queryKey: ['doctor'] });
    await queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
  };

  const decide = useMutation({
    mutationFn: async (input: { item: ReviewCase; action: string; doctorId?: string; comment: string; board?: boolean }) => {
      if (input.board || !input.item.review_id) {
        return resolveBoardItem({ item_id: input.item.id, action: input.action, comment: input.comment });
      }
      return submitDecision(input.item.review_id, {
        action: input.action,
        decision: input.action,
        selected_doctor_id: input.doctorId,
        comment: input.comment,
        expected_version: input.item.version,
        idempotency_key: newIdempotencyKey(),
      });
    },
    onSuccess: async (_data, input) => {
      const doctorId = input.doctorId || input.item.doctor_id;
      setLeaving(input.item.id);
      setToast({
        text: `${input.item.record_id} updated`,
        href: doctorId ? `/doctors/${doctorId}` : undefined,
        label: doctorId ? 'View doctor' : undefined,
      });
      window.setTimeout(() => {
        setLeaving(null);
        void refresh();
      }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 320);
    },
  });

  function confirmLink(item: ReviewCase, doctorId: string) {
    const recommended = item.candidates.find((row) => row.recommended)?.doctor_id;
    if (doctorId !== recommended && !reason.trim()) {
      setReasonError(true);
      return;
    }
    decide.mutate({
      item,
      action: item.link_action || 'approve',
      doctorId,
      comment: reason.trim() || 'Reviewer accepted the recommendation',
    });
    setPreviewDoctor(null);
  }

  const sim = simulator.data || {};
  const histogram = (sim.histogram as Array<{ from: number; count: number; right?: number | null; wrong?: number | null }>) || [];
  const maxBar = Math.max(1, ...histogram.map((bar) => bar.count || 0));
  const measurable = Boolean(sim.measurable);

  if (board.isError) return <ErrorState message={(board.error as Error).message} onRetry={() => board.refetch()} />;

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div className="card">
        <div className="card-b try">
          <b style={{ whiteSpace: 'nowrap' }}>Try a record</b>
          <input
            value={tryText}
            onChange={(event) => setTryText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') void tryRecord();
            }}
            placeholder='e.g. "Dr. S Lee, LCI Oncology, Chicago"'
            aria-label="Try a record"
          />
          <button type="button" className="btn primary" onClick={() => void tryRecord()}>
            Find matches
          </button>
          <span className="faint" style={{ fontSize: 12.5 }}>Nothing is saved</span>
        </div>
        {trying ? (
          <div className="card-b" style={{ display: 'grid', gap: 8 }}>
            <div className="skel" style={{ width: '60%' }} />
            <div className="skel" style={{ width: '85%' }} />
          </div>
        ) : null}
        {tryError ? <p className="card-b" style={{ color: 'var(--bad)' }}>{tryError}</p> : null}
        {tryResult ? (
          <div className="card-b" style={{ paddingTop: 0 }}>
            <div className="cands">
              {tryResult.map((row, index) => (
                <Link key={row.doctor_id || index} className="cand" to={`/doctors/${row.doctor_id}`}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <b>{row.name}</b>
                    {index === 0 ? <span className="pill ok">Best match</span> : null}
                  </div>
                  <span className="muted">{[row.city, row.state].filter(Boolean).join(', ')} · {row.specialty}</span>
                  <span className="score">{Number(row.score || 0).toFixed(2)}</span>
                  <span className="muted" style={{ fontSize: 12.5 }}>
                    {row.reasons?.length ? `Matched on ${row.reasons.join(', ')}` : 'Weak match'}
                  </span>
                </Link>
              ))}
              {!tryResult.length ? <p className="muted">No stored doctor matches that text.</p> : null}
            </div>
          </div>
        ) : null}
      </div>

      <div className="card" id="simCard" data-tour="simulator">
        <details className="sim" open={simOpen} onToggle={(event) => setSimOpen((event.target as HTMLDetailsElement).open)}>
          <summary className="card-h" style={{ paddingBottom: 16 }}>
            <h2>Automation control</h2>
            <span className="hint">
              Auto-link threshold {threshold.toFixed(2)} · {String(sim.automatic ?? '—')} linked automatically
              {measurable ? ` · ${String(sim.overmerges ?? 0)} wrong on test data` : ''}
            </span>
            <span className="link right">{simOpen ? 'Hide' : 'Adjust threshold'}</span>
          </summary>
          <div className="card-b" style={{ paddingTop: 0, display: 'grid', gap: 14 }}>
            <div className="simrow">
              <div style={{ display: 'grid', gap: 12 }}>
                <label htmlFor="simR" style={{ display: 'grid', gap: 6 }}>
                  <span className="muted">
                    Auto-link when the score is at least <b style={{ color: 'var(--fg)' }}>{threshold.toFixed(2)}</b> and the lead over the next doctor is {Number(sim.margin ?? 0.05).toFixed(2)} or more
                  </span>
                  <input id="simR" type="range" min={0.5} max={0.99} step={0.01} value={threshold} onChange={(event) => setThreshold(Number(event.target.value))} />
                </label>
                <div className="simstats">
                  <div>
                    <b>
                      {String(sim.automatic ?? '—')}
                      {Number(sim.automatic_delta) ? <small style={{ fontSize: 12, color: Number(sim.automatic_delta) > 0 ? 'var(--ok)' : 'var(--bad)' }}> {Number(sim.automatic_delta) > 0 ? '+' : ''}{String(sim.automatic_delta)}</small> : null}
                    </b>
                    <span>Linked automatically</span>
                  </div>
                  <div>
                    <b>
                      {String(sim.to_people ?? '—')}
                      {Number(sim.to_people_delta) ? <small style={{ fontSize: 12 }}> {Number(sim.to_people_delta) > 0 ? '+' : ''}{String(sim.to_people_delta)}</small> : null}
                    </b>
                    <span>Sent to people</span>
                  </div>
                  <div style={measurable && Number(sim.overmerges) ? { background: 'var(--bad-bg)', borderColor: 'var(--bad)' } : undefined}>
                    <b style={measurable && Number(sim.overmerges) ? { color: 'var(--bad)' } : undefined}>{measurable ? String(sim.overmerges ?? 0) : '—'}</b>
                    <span>Wrong links (overmerges)</span>
                  </div>
                  <div>
                    <b>{measurable && sim.precision != null ? `${(Number(sim.precision) * 100).toFixed(1)}%` : '—'}</b>
                    <span>Precision of automatic links</span>
                  </div>
                </div>
                {!measurable ? <p className="muted" style={{ margin: 0 }}>{String(sim.message || 'Accuracy cannot be measured yet.')}</p> : null}
              </div>
              <div className="hist" aria-hidden>
                <svg viewBox="0 0 520 170" role="img" aria-label="Score distribution with threshold">
                  {histogram.map((bar, index) => {
                    const height = ((bar.count || 0) / maxBar) * 120;
                    const right = measurable ? bar.right || 0 : bar.count || 0;
                    const wrong = measurable ? bar.wrong || 0 : 0;
                    const rightH = ((right || 0) / maxBar) * 120;
                    const wrongH = ((wrong || 0) / maxBar) * 120;
                    return (
                      <g key={bar.from}>
                        <rect x={24 + index * 48 + 2} y={146 - rightH} width={40} height={rightH} fill="var(--ok)" opacity={0.75} />
                        <rect x={24 + index * 48 + 2} y={146 - rightH - wrongH} width={40} height={wrongH} fill="var(--bad)" />
                        {!measurable ? <rect x={24 + index * 48 + 2} y={146 - height} width={40} height={height} fill="var(--accent)" opacity={0.35} /> : null}
                      </g>
                    );
                  })}
                  <line x1="24" x2="496" y1="146" y2="146" stroke="var(--line-2)" />
                  <text x={24 + ((threshold - 0.5) / 0.5) * 450} y="20" fill="var(--accent)">threshold {threshold.toFixed(2)}</text>
                </svg>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <span className="faint" style={{ fontSize: 12.5 }}>
                {measurable
                  ? 'Measured on stored scores and labels. Payments always go to compliance and are not counted. Simulation only.'
                  : 'Payments always go to compliance and are not counted. Simulation only. Accuracy cannot be measured until labels exist.'}
              </span>
              <button
                type="button"
                className="btn sm"
                style={{ marginLeft: 'auto' }}
                onClick={async () => {
                  await apiFetch('/quality/threshold-proposals', { method: 'POST', body: JSON.stringify({ threshold }) });
                  setToast({ text: 'Threshold change submitted for approval' });
                }}
              >
                Propose this threshold
              </button>
            </div>
          </div>
        </details>
      </div>

      {board.data?.needs_run ? (
        <div className="card">
          <div className="empty">
            <b>Nothing to review yet</b>
            <span>Run historical cleanup first.</span>
          </div>
        </div>
      ) : (
        <div className="rv">
          <div className="card queue">
            <div className="card-h">
              <h2>Queue</h2>
              <span className="hint">{visible.length} of {items.length}</span>
              <div className="seg sm right" aria-label="Group by">
                <button type="button" className={group === 'issue' ? 'on' : ''} onClick={() => setParams((current) => { const next = new URLSearchParams(current); next.delete('group'); return next; })}>By issue</button>
                <button type="button" className={group === 'doctor' ? 'on' : ''} onClick={() => setParams((current) => { const next = new URLSearchParams(current); next.set('group', 'doctor'); return next; })}>By doctor</button>
              </div>
            </div>
            <div className="card-b" style={{ paddingBottom: 10 }}>
              <div className="chips">
                {FILTERS.map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    className={`chip ${filter === key ? 'on' : ''}`}
                    onClick={() => setParams((current) => {
                      const next = new URLSearchParams(current);
                      if (key === 'all') next.delete('filter');
                      else next.set('filter', key);
                      next.delete('case');
                      return next;
                    })}
                  >
                    {label}<span className="c">{counts[key] || 0}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="qlist">
              {groups.length ? groups.map(([key, rows]) => (
                <div key={key}>
                  <div className="qgh"><span>{key}</span><span>{rows.length}</span></div>
                  {rows.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={`qi ${selected?.id === item.id ? 'on' : ''} ${leaving === item.id ? 'out' : ''}`}
                      onClick={() => choose(item.id)}
                    >
                      <b>{item.question}</b>
                      <span className="m">
                        <span className={`pill ${item.risk_tone}`}>{item.risk}</span>
                        <span>{item.type_label}</span>
                        <span>· {item.source_label}</span>
                        {item.amount ? <span>· {money(item.amount)}</span> : null}
                      </span>
                    </button>
                  ))}
                </div>
              )) : (
                <div className="empty"><b>All clear</b><span>No decisions waiting in this filter.</span></div>
              )}
            </div>
          </div>
          <div style={{ display: 'grid', gap: 16, minWidth: 0 }}>
            {selected ? (
              <CaseDetail
                item={selected}
                candidateId={candidateId}
                onCandidate={setCandidateId}
                previewDoctor={previewDoctor}
                onPreview={setPreviewDoctor}
                reason={reason}
                reasonError={reasonError}
                onReason={(value) => { setReason(value); setReasonError(false); }}
                busy={decide.isPending}
                error={decide.isError ? (decide.error as Error).message : null}
                onConfirm={(doctorId) => confirmLink(selected, doctorId)}
                onCancel={() => setPreviewDoctor(null)}
                onBoard={(action, comment, useBoard = true) => decide.mutate({ item: selected, action, comment, board: useBoard || !selected.review_id, doctorId: selected.doctor_id || undefined })}
                onSoft={(message) => setToast({ text: message })}
              />
            ) : (
              <div className="card"><div className="empty"><b>No decision selected</b><span>Pick a case from the queue.</span></div></div>
            )}
          </div>
        </div>
      )}
      {toast ? (
        <div className="toast" role="status">
          <span>{toast.text}</span>
          {toast.href ? <Link className="link" to={toast.href} onClick={() => setToast(null)}>{toast.label}</Link> : null}
          <button type="button" className="iconbtn" aria-label="Dismiss" onClick={() => setToast(null)} style={{ color: '#fff' }}>×</button>
        </div>
      ) : null}
    </div>
  );
}

function CaseDetail({
  item,
  candidateId,
  onCandidate,
  previewDoctor,
  onPreview,
  reason,
  reasonError,
  onReason,
  busy,
  error,
  onConfirm,
  onCancel,
  onBoard,
  onSoft,
}: {
  item: ReviewCase;
  candidateId: string | null;
  onCandidate: (id: string) => void;
  previewDoctor: string | null;
  onPreview: (id: string | null) => void;
  reason: string;
  reasonError: boolean;
  onReason: (value: string) => void;
  busy: boolean;
  error: string | null;
  onConfirm: (doctorId: string) => void;
  onCancel: () => void;
  onBoard: (action: string, comment: string, useBoard?: boolean) => void;
  onSoft: (message: string) => void;
}) {
  const record = item.record;
  const head = (
    <div className="card">
      <div className="card-b" style={{ display: 'grid', gap: 12 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <span className={`pill ${item.risk_tone}`}>{item.risk} risk</span>
          <span className="pill outline">{item.type_label}</span>
          <span className="mono faint">{item.record_id}</span>
        </div>
        <h2 style={{ margin: 0, fontSize: 19 }}>{item.question}</h2>
        {item.queue_type === 'compliance' ? (
          <div className="banner bad">Payment record: only compliance reviewers can approve. Filed Open Payments values are never changed automatically.</div>
        ) : null}
        {record.quote ? <div className="quote">{record.quote}</div> : null}
        <div className="rec">
          <div><span>Source</span>{record.source}</div>
          <div><span>Name as written</span><b>{record.name || <i className="faint">blank</i>}</b></div>
          <div>
            <span>Stated NPI</span>
            <span className="mono" style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 400, color: 'var(--fg)', fontSize: 12.5 }}>{record.npi || 'none'}</span>
            {record.npi_label ? <span className={`pill ${npiTone(record.npi_label)}`}>{record.npi_label}</span> : null}
          </div>
          <div><span>Specialty</span>{record.specialty || <i className="faint">missing</i>}</div>
          <div><span>Practice</span>{record.practice || <i className="faint">missing</i>}</div>
          <div><span>Location</span>{location(record.city, record.state) || <i className="faint">missing</i>}</div>
          <div><span>Date</span>{record.date || '—'}</div>
          {record.amount != null ? <div><span>Amount</span>{money(record.amount)}</div> : null}
        </div>
      </div>
    </div>
  );

  if (item.queue_type === 'safety' && item.safety) {
    const quote = item.safety.quote || '';
    const phrase = item.safety.highlight || '';
    const marked = phrase && quote.toLowerCase().includes(phrase) ? quote.replace(new RegExp(phrase, 'i'), (match) => `[[${match}]]`) : quote;
    return (
      <>
        {head}
        <div className="card">
          <div className="card-b" style={{ display: 'grid', gap: 12 }}>
            <div className="banner bad">Possible adverse event detected. It stays visible and must be routed to pharmacovigilance.</div>
            <div className="quote">
              {marked.split('[[').map((part, index) => {
                if (!part.includes(']]')) return <span key={index}>{part}</span>;
                const [hit, rest] = part.split(']]');
                return <span key={index}><mark>{hit}</mark>{rest}</span>;
              })}
            </div>
            <div className="reason">
              <h4>AI reasoning</h4>
              <p style={{ margin: 0 }}>
                {item.safety.reason} Patient details were removed before analysis.
                {item.safety.doctor_name ? <> The doctor mention resolves to <Link className="link" to={`/doctors/${item.safety.doctor_id}`}>{item.safety.doctor_name}</Link>.</> : null}
              </p>
            </div>
            <div className="chips">
              <button type="button" className="btn primary" disabled={busy} onClick={() => onBoard('route_safety', 'Possible adverse event routed to pharmacovigilance')}>Route to pharmacovigilance</button>
              <button type="button" className="btn" onClick={() => onSoft(`${item.record_id} deferred`)}>Defer</button>
            </div>
            {error ? <p style={{ color: 'var(--bad)', margin: 0 }}>{error}</p> : null}
          </div>
        </div>
      </>
    );
  }

  if (item.queue_type === 'proposed' && item.proposed) {
    return (
      <>
        {head}
        <div className="card">
          <div className="card-h">
            <h3>Proposed change for {item.proposed.doctor_id ? <Link className="link" to={`/doctors/${item.proposed.doctor_id}`}>{item.proposed.doctor_name}</Link> : item.proposed.doctor_name}</h3>
          </div>
          <div className="card-b" style={{ display: 'grid', gap: 12 }}>
            <div className="tw">
              <table>
                <thead><tr><th>Field</th><th>Current value</th><th>Proposed value</th></tr></thead>
                <tbody>
                  <tr>
                    <td>{item.proposed.field}</td>
                    <td className="muted">{item.proposed.current}</td>
                    <td><b>{item.proposed.proposed}</b></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="reason">
              <h4>Evidence</h4>
              <p style={{ margin: 0 }}>Quoted from note {item.record_id}: <mark style={{ background: '#ffe9b8' }}>{item.proposed.quote}</mark></p>
              <p className="muted" style={{ margin: 0 }}>One source only, so it needs approval before the golden record changes.</p>
            </div>
            <div className="chips">
              <button type="button" className="btn primary" disabled={busy} onClick={() => onBoard('approve_change', 'Proposed change approved')}>Approve change</button>
              <button type="button" className="btn" disabled={busy} onClick={() => onBoard('reject_change', 'Reviewer rejected the proposed change')}>Reject</button>
              <button type="button" className="btn" onClick={() => onSoft(`${item.record_id} deferred`)}>Defer</button>
            </div>
            {error ? <p style={{ color: 'var(--bad)', margin: 0 }}>{error}</p> : null}
          </div>
        </div>
      </>
    );
  }

  const candidates = item.candidates || [];
  const reasoning = item.reasoning;
  const recommendedId = candidates.find((row) => row.recommended)?.doctor_id;
  return (
    <>
      {head}
      {candidates.length ? (
        <>
          <div className="card" data-tour="candidates">
            <div className="card-h"><h3>Candidate doctors</h3><span className="hint">Ranked by match score · click to compare</span></div>
            <div className="card-b">
              <div className="cands">
                {candidates.map((candidate, index) => (
                  <button key={candidate.doctor_id || index} type="button" className={`cand ${candidateId === candidate.doctor_id ? 'on' : ''}`} onClick={() => candidate.doctor_id && onCandidate(candidate.doctor_id)}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                      <b>{candidate.name}</b>
                      {candidate.recommended ? <span className="pill ok">Recommended</span> : null}
                      {candidate.no_clear_winner && index === 0 ? <span className="pill warn">No clear winner</span> : null}
                    </div>
                    <span className="muted mono" style={{ fontSize: 12 }}>NPI {candidate.npi || 'none'}</span>
                    <span className="muted">{candidate.specialty} · {location(candidate.city, candidate.state)}</span>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                      <span className="score" style={{ color: scoreColor(candidate.score) }}>{Number(candidate.score || 0).toFixed(2)}</span>
                      <span className="muted">match score</span>
                    </div>
                    <div className="meter"><i style={{ width: `${Math.min(100, Number(candidate.score || 0) * 100)}%`, background: scoreColor(candidate.score) }} /></div>
                  </button>
                ))}
              </div>
              {candidates.length < 3 ? <p className="muted" style={{ margin: '10px 0 0', fontSize: 12.5 }}>Only {candidates.length} plausible doctor{candidates.length > 1 ? 's' : ''} found.</p> : null}
            </div>
          </div>
          <div className="card">
            <div className="card-h"><h3>Field comparison</h3><span className="hint">✓ match · ≈ partial · ✗ conflict · — missing</span></div>
            <div className="card-b tw">
              <table className="cmp">
                <thead>
                  <tr>
                    <th>Field</th>
                    <th>This record</th>
                    {candidates.map((candidate) => (
                      <th key={candidate.doctor_id} style={{ color: candidate.doctor_id === candidateId ? 'var(--accent)' : undefined }}>
                        {candidate.name} · {candidate.city}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {FIELDS.map((field) => (
                    <tr key={field}>
                      <td className="muted">{field}</td>
                      <td>{recordValue(item, field) || <span className="faint">—</span>}</td>
                      {candidates.map((candidate) => {
                        const cell = candidate.grid?.[field] || ['—', 'Not compared'];
                        return (
                          <td key={candidate.doctor_id} className="v" style={{ background: candidate.doctor_id === candidateId ? '#f5f8fd' : undefined }}>
                            <span className={`sym ${symClass(cell[0])}`}>{cell[0]}</span>
                            {doctorValue(candidate, field)}
                            <div className="faint" style={{ fontSize: 12, marginLeft: 28 }}>{cell[1]}</div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="card" id="reasonCard" data-tour="reasoning">
            <div className="card-b" style={{ display: 'grid', gap: 12 }}>
              {reasoning ? (
                <div className="reason">
                  <h4>AI reasoning · recommendation only</h4>
                  <p style={{ margin: 0 }}>
                    <b>{reasoning.recommendation}</b>{' '}
                    <span className={`pill ${reasoning.confidence === 'High' ? 'ok' : reasoning.confidence === 'Medium' ? 'warn' : 'neu'}`}>{reasoning.confidence} confidence</span>
                  </p>
                  {reasoning.extra.map((line) => <p key={line} style={{ margin: 0 }}>{line}</p>)}
                  <ul>
                    {reasoning.agrees.length ? <li><b>Agrees:</b> {reasoning.agrees.join('; ')}</li> : null}
                    {reasoning.partial.length ? <li><b>Partly agrees:</b> {reasoning.partial.join('; ')}</li> : null}
                    {reasoning.conflicts.length ? <li><b>Conflicts to check:</b> {reasoning.conflicts.join('; ')}</li> : null}
                    {reasoning.why_not.length ? <li><b>Why not the others:</b> {reasoning.why_not.join(' · ')}</li> : null}
                  </ul>
                  <details className="how">
                    <summary>Score breakdown and how this was found</summary>
                    <p style={{ margin: '6px 0 0' }}>
                      Found by: {reasoning.found_by}. Margin over next candidate: {reasoning.margin.toFixed(2)}. Model: Splink. Evidence cited: {item.record_id}
                      {candidates.map((row) => row.doctor_id).filter(Boolean).join(', ') ? `, ${candidates.map((row) => row.name).join(', ')}` : ''}.
                    </p>
                  </details>
                </div>
              ) : null}
              <div className="chips">
                {candidates.map((candidate) => (
                  <button
                    key={candidate.doctor_id}
                    type="button"
                    className={`btn ${candidate.doctor_id === recommendedId ? 'primary' : ''}`}
                    disabled={busy || item.link_blocked || !item.review_id}
                    title={item.link_blocked ? 'A hard stop blocks linking this record' : undefined}
                    onClick={() => candidate.doctor_id && onPreview(candidate.doctor_id)}
                  >
                    {item.queue_type === 'compliance' ? 'Approve as' : 'Link to'} {candidate.name}{candidate.city ? ` · ${candidate.city}` : ''}
                  </button>
                ))}
                <button type="button" className="btn" disabled={busy} onClick={() => onBoard(item.review_id ? 'leave_unresolved' : 'leave_unmatched', 'No candidate fits', !item.review_id)}>None of these</button>
                <button type="button" className="btn" onClick={() => onSoft(`Requested more information for ${item.record_id}`)}>Need more information</button>
                <button type="button" className="btn ghost" onClick={() => onSoft(`${item.record_id} deferred`)}>Defer</button>
              </div>
              {item.link_blocked ? <p className="muted" style={{ margin: 0 }}>A hard stop blocks a link. Leave the record unmatched or defer it.</p> : null}
              {error ? <p style={{ color: 'var(--bad)', margin: 0 }}>{error}</p> : null}
              {previewDoctor ? (
                <div className="preview">
                  <b>What will change</b>
                  <ul>
                    <li>
                      {item.source_label} {item.record_id} is linked to <b>{candidates.find((row) => row.doctor_id === previewDoctor)?.name}</b>
                      {candidates.find((row) => row.doctor_id === previewDoctor)?.npi ? ` (NPI ${candidates.find((row) => row.doctor_id === previewDoctor)?.npi})` : ''} and appears as New on the doctor&apos;s records and timeline.
                    </li>
                    {item.queue_type === 'compliance' ? <li>A correction is logged for compliance. The filed Open Payments value is not changed automatically.</li> : <li>The source file is not changed.</li>}
                    <li>The AI summary is regenerated.</li>
                  </ul>
                  {previewDoctor !== recommendedId ? (
                    <label style={{ display: 'grid', gap: 6 }}>
                      <span className="muted">This is not the recommended doctor. Reason (required)</span>
                      <textarea id="why" rows={2} value={reason} onChange={(event) => onReason(event.target.value)} style={{ border: `1px solid ${reasonError ? 'var(--bad)' : 'var(--line-2)'}`, borderRadius: 8, padding: '8px 10px' }} placeholder="e.g. confirmed by attendance list" />
                    </label>
                  ) : null}
                  <div className="chips">
                    <button type="button" className="btn primary" disabled={busy} onClick={() => onConfirm(previewDoctor)}>Confirm</button>
                    <button type="button" className="btn" onClick={onCancel}>Cancel</button>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </>
      ) : (
        <div className="card">
          <div className="empty">
            <b>No plausible doctors found</b>
            <span>Not enough information to suggest a match.</span>
            <div className="chips">
              <button type="button" className="btn primary" disabled={busy} onClick={() => onBoard(item.review_id ? 'leave_unresolved' : 'leave_unmatched', 'No candidate fits', !item.review_id)}>Leave unmatched</button>
              <button type="button" className="btn" onClick={() => onSoft(`Requested more information for ${item.record_id}`)}>Need more information</button>
            </div>
            {error ? <p style={{ color: 'var(--bad)' }}>{error}</p> : null}
          </div>
        </div>
      )}
    </>
  );
}
