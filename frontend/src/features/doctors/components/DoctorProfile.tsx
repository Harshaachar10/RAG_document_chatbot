import { useQuery } from '@tanstack/react-query';
import * as Tabs from '@radix-ui/react-tabs';
import { X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { fetchProfileSummary } from '../../../api/ai';
import { apiFetch } from '../../../api/client';
import {
  fetchDoctor,
  fetchDoctorHistory,
  fetchDoctorSourceRecords,
  fetchMatchExplanation,
} from '../../../api/doctors';
import { ErrorState } from '../../../components/ErrorState';
import { Skeleton } from '../../../components/Skeleton';
import { StatusBadge } from '../../../components/StatusBadge';
import { displayValue } from '../../../utils/formatters';
import { AskPanel } from '../../../components/AskPanel';
import { DoctorTimeline } from './DoctorTimeline';
import { EvidenceWorkspace } from './EvidenceWorkspace';
import { LinkedRecordsTable } from './LinkedRecordsTable';
import { MatchExplanation } from './MatchExplanation';
import { ProfileSummary } from './ProfileSummary';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'records', label: 'Records' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'lineage', label: 'Lineage' },
  { id: 'impact', label: 'Prescriber impact' },
  { id: 'payments', label: 'Payments' },
  { id: 'separate', label: 'Kept separate' },
  { id: 'changes', label: 'History' },
  { id: 'ask', label: 'Ask' },
] as const;

const TAB_ALIAS: Record<string, string> = {
  summary: 'overview',
  known: 'overview',
  linked: 'records',
  history: 'timeline',
  similar: 'separate',
};

export function DoctorProfile({
  doctorId,
  tab = 'summary',
  onTabChange,
  mode = 'page',
  onClose,
  eventId,
  evidenceId: initialEvidenceId,
}: {
  doctorId: string;
  tab?: string;
  onTabChange?: (tab: string) => void;
  mode?: 'page' | 'drawer';
  onClose?: () => void;
  expandTo?: string;
  eventId?: string | null;
  evidenceId?: string | null;
}) {
  const activeTab = TAB_ALIAS[tab] || (tab === 'match' || tab === 'reviews' ? 'overview' : tab);
  const [aliasFilter, setAliasFilter] = useState<string | null>(null);
  const [evidenceId, setEvidenceId] = useState<string | null>(initialEvidenceId || null);
  const [mobileEvidence, setMobileEvidence] = useState(false);
  const [highlightGapsFor, setHighlightGapsFor] = useState<string | null>(null);
  const [lens, setLens] = useState<'golden' | 'raw'>('golden');

  const doctorQuery = useQuery({
    queryKey: ['doctor', doctorId],
    queryFn: ({ signal }) => fetchDoctor(doctorId, signal),
  });
  const recordsQuery = useQuery({
    queryKey: ['doctor-records', doctorId],
    queryFn: ({ signal }) => fetchDoctorSourceRecords(doctorId, signal),
  });
  const historyQuery = useQuery({
    queryKey: ['doctor-history', doctorId],
    queryFn: ({ signal }) => fetchDoctorHistory(doctorId, {}, signal),
  });
  const matchQuery = useQuery({
    queryKey: ['doctor-match', doctorId],
    queryFn: ({ signal }) => fetchMatchExplanation(doctorId, signal),
  });

  const evidenceList = useMemo(() => {
    const ids = new Set<string>();
    (recordsQuery.data?.items || []).forEach((r) => r.evidence_ids.forEach((id) => ids.add(id)));
    (historyQuery.data?.items || []).forEach((e) => {
      if (e.evidence_id) ids.add(e.evidence_id);
    });
    return Array.from(ids);
  }, [recordsQuery.data, historyQuery.data]);

  const openEvidence = (id: string, sourceRecordId?: string | null) => {
    setEvidenceId(id);
    setHighlightGapsFor(sourceRecordId || null);
    setMobileEvidence(true);
    onTabChange?.('evidence');
  };

  if (doctorQuery.isLoading) return <Skeleton className="h-96 w-full" />;
  if (doctorQuery.isError) {
    return <ErrorState message={(doctorQuery.error as Error).message} onRetry={() => doctorQuery.refetch()} />;
  }
  const doctor = doctorQuery.data!;
  const highlightedRecord = (recordsQuery.data?.items || []).find((r) => r.source_record_id === highlightGapsFor);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="border-b border-border bg-white px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold">{doctor.preferred_name}</h1>
            <p className="mt-1 text-sm text-muted">
              NPI {displayValue(doctor.official_npi)} · {doctor.npi_status} · {displayValue(doctor.specialty)} · {[doctor.city, doctor.state].filter(Boolean).join(', ') || 'Location not available'}
            </p>
            {doctor.evidence_summary ? <p className="mt-1 text-sm">{doctor.evidence_summary}</p> : null}
            {(doctor.alarms || []).length ? (
              <div className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-950" role="alert">
                Safety alarm. {(doctor.alarms || []).map((alarm) => String(alarm.reason || 'Possible adverse event')).join(' ')}
                {(doctor.alarms || [])[0]?.quote ? ` “${String((doctor.alarms || [])[0].quote)}”` : ''}
              </div>
            ) : null}
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              <span className="text-xs text-muted">Master {doctor.doctor_id}</span>
              <StatusBadge value={doctor.identity_review_status === 'pending' ? 'pending' : 'clear'} kind="review" />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="self-center text-xs text-muted">Also recorded as:</span>
              {doctor.aliases.map((a) => {
                const name = String(a.name);
                const selected = aliasFilter === name;
                return (
                  <button
                    key={String(a.alias_id)}
                    type="button"
                    onClick={() => setAliasFilter(selected ? null : name)}
                    className={`rounded-full border px-2.5 py-0.5 text-xs ${
                      selected ? 'border-primary bg-primary text-white' : 'border-border bg-white text-foreground'
                    }`}
                    aria-pressed={selected}
                  >
                    {name}
                  </button>
                );
              })}
            </div>
            <div className="mt-2 text-xs text-muted">
              Linked records: {doctor.linked_record_count} · Sources: {doctor.source_count} · Pending changes: {doctor.pending_field_changes}
            </div>
            <div className="mt-3">
              <StoredSummary doctorId={doctorId} brief={doctor.profile_brief} />
            </div>
          </div>
          <div className="flex items-center gap-2 acts">
            <div className="seg sm" role="group" aria-label="Record view">
              <button type="button" className={lens === 'golden' ? 'on' : ''} data-tour="golden-view" onClick={() => setLens('golden')}>Golden record</button>
              <button type="button" className={lens === 'raw' ? 'on' : ''} data-tour="raw-view" onClick={() => setLens('raw')}>What your systems show today</button>
            </div>
            {mode === 'drawer' && onClose ? (
              <button type="button" onClick={onClose} className="rounded-md p-1.5 hover:bg-slate-100" aria-label="Close">
                <X size={16} />
              </button>
            ) : null}
          </div>
        </div>
      </header>

      {lens === 'raw' ? (
        <div id="rawPanel" className="space-y-3 p-4" data-tour="raw-panel">
          <div className="rawstrip">
            <div><b>{recordsQuery.data?.items.length || 0}</b><span>records as written</span></div>
          </div>
          <div className="rawgrid">
            {(recordsQuery.data?.items || []).map((row) => (
              <article key={row.source_record_id} className="rawcard">
                <div className="s"><span>{row.source_name || row.source_id}</span><span className="mono">{row.source_record_id}</span></div>
                <b>{row.recorded_name || 'Name not on record'}</b>
                <div className="r">{row.practice_name || 'Practice not on record'}</div>
                <div className="r">{[row.city, row.state].filter(Boolean).join(', ') || 'Location not on record'}</div>
                <div className="r">NPI {row.provider_identifier || 'not on record'}</div>
              </article>
            ))}
          </div>
          <button type="button" className="btn" onClick={() => setLens('golden')}>Back to the golden record</button>
        </div>
      ) : null}
      {lens === 'golden' ? (
      <Tabs.Root
        value={activeTab}
        onValueChange={(v) => onTabChange?.(v)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <Tabs.List className="flex flex-wrap gap-1 border-b border-border bg-slate-50 px-2 py-2" aria-label="Doctor profile tabs">
          {TABS.map((t) => (
            <Tabs.Trigger
              key={t.id}
              value={t.id}
              data-tour={t.id === 'separate' ? 'kept-separate' : undefined}
              className="rounded-md px-3 py-1.5 text-sm data-[state=active]:bg-white data-[state=active]:font-semibold data-[state=active]:shadow-sm"
            >
              {t.label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <div className="min-h-0 flex-1 overflow-auto p-4">
          <Tabs.Content value="overview">
            <div className="space-y-4">
              <ProfileSummary doctor={doctor} onViewEvidence={() => onTabChange?.('lineage')} />
              <KnownValues doctorId={doctorId} />
            </div>
          </Tabs.Content>
          <Tabs.Content value="records">
            {recordsQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
            {recordsQuery.data ? (
              <LinkedRecordsTable
                records={recordsQuery.data.items}
                onOpenEvidence={(id) => {
                  const rec = recordsQuery.data.items.find((r) => r.evidence_ids.includes(id));
                  openEvidence(id, rec?.source_record_id);
                }}
                onOpenRecord={(rec) => {
                  if (rec.evidence_ids[0]) openEvidence(rec.evidence_ids[0], rec.source_record_id);
                }}
                aliasFilter={aliasFilter}
              />
            ) : null}
          </Tabs.Content>
          <Tabs.Content value="timeline">
            {historyQuery.data ? (
              <DoctorTimeline events={historyQuery.data.items} highlightEventId={eventId} onOpenEvidence={() => undefined} />
            ) : (
              <Skeleton className="h-40 w-full" />
            )}
          </Tabs.Content>
          <Tabs.Content value="lineage">
            <LineageGraph doctorId={doctorId} />
          </Tabs.Content>
          <Tabs.Content value="impact">
            <PrescriberImpact records={recordsQuery.data?.items || []} />
          </Tabs.Content>
          <Tabs.Content value="payments">
            <PaymentsList records={(recordsQuery.data?.items || []).filter((row) => row.source_id === 'payments')} />
          </Tabs.Content>
          <Tabs.Content value="separate">
            <SimilarRecords doctorId={doctorId} />
          </Tabs.Content>
          <Tabs.Content value="changes">
            {historyQuery.data ? (
              <DoctorTimeline events={historyQuery.data.items} highlightEventId={eventId} onOpenEvidence={() => undefined} />
            ) : (
              <Skeleton className="h-40 w-full" />
            )}
          </Tabs.Content>
          <Tabs.Content value="ask">
            <AskPanel doctorId={doctorId} title="Ask about this doctor" />
          </Tabs.Content>
          <Tabs.Content value="history">
            {historyQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
            {historyQuery.data ? (
              <DoctorTimeline
                events={historyQuery.data.items}
                highlightEventId={eventId}
                onOpenEvidence={(id) => {
                  const evt = historyQuery.data.items.find((e) => e.evidence_id === id);
                  openEvidence(id, evt?.source_record_id);
                }}
                trailSummary={historyQuery.data.trail_summary}
              />
            ) : null}
          </Tabs.Content>
          <Tabs.Content value="evidence">
            <div className="space-y-4">
              {matchQuery.data ? (
                <MatchExplanation
                  data={matchQuery.data}
                  onOpenEvidence={openEvidence}
                  onOpenSourceRecord={(sourceRecordId) => {
                    const rec = (recordsQuery.data?.items || []).find((r) => r.source_record_id === sourceRecordId);
                    if (rec?.evidence_ids[0]) openEvidence(rec.evidence_ids[0], sourceRecordId);
                  }}
                />
              ) : null}
              {highlightedRecord ? (
                <section className="rounded-[12px] border border-amber-200 bg-amber-50 p-3 text-sm">
                  <h4 className="font-semibold text-amber-950">Highlighted source record {highlightedRecord.source_record_id}</h4>
                  <p className="mt-1">
                    Provided: {displayValue(highlightedRecord.recorded_name)} · {displayValue(highlightedRecord.practice_name)} ·{' '}
                    {displayValue(highlightedRecord.provider_identifier, 'NPI missing')}
                  </p>
                  <p className="mt-1 text-amber-900">
                    Missing:{' '}
                    {[
                      !highlightedRecord.provider_identifier || highlightedRecord.identifier_kind === 'missing' ? 'NPI' : null,
                      !highlightedRecord.address_line ? 'Address' : null,
                      !highlightedRecord.email && !highlightedRecord.phone ? 'Contact' : null,
                    ].filter(Boolean).join(', ') || 'None highlighted'}
                  </p>
                </section>
              ) : null}
              <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
                <div className={`rounded-[12px] border border-border bg-white p-3 ${mobileEvidence ? 'hidden lg:block' : ''}`}>
                  <h3 className="text-sm font-semibold">Evidence list</h3>
                  <ul className="mt-3 space-y-1">
                    {evidenceList.map((id) => (
                      <li key={id}>
                        <button
                          type="button"
                          className={`w-full rounded-md px-2 py-1.5 text-left text-sm ${evidenceId === id ? 'bg-primary text-white' : 'hover:bg-slate-50'}`}
                          onClick={() => {
                            setEvidenceId(id);
                            setMobileEvidence(true);
                          }}
                        >
                          {id}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className={`${!mobileEvidence ? 'hidden lg:block' : ''}`}>
                  <EvidenceWorkspace evidenceId={evidenceId || evidenceList[0]} onBack={() => setMobileEvidence(false)} />
                </div>
              </div>
            </div>
          </Tabs.Content>
        </div>
      </Tabs.Root>
      ) : null}
    </div>
  );
}

function StoredSummary({ doctorId, brief }: { doctorId: string; brief?: string | null }) {
  const cached = useQuery({
    queryKey: ['doctor-ai-summary', doctorId],
    queryFn: ({ signal }) => fetchProfileSummary(doctorId, signal),
    refetchInterval: (query) => (query.state.data?.available ? false : 15000),
  });
  const analysis = cached.data?.analysis?.response as { summary?: string; current_profile?: string; affiliation_summary?: string } | undefined;
  const modelText = analysis?.summary;
  return (
    <section className="ai" data-tour="ai-summary">
      <h3 className="text-sm font-semibold">Profile summary</h3>
      <p className="mt-2 text-sm">{modelText || brief || 'Summary is stored with this doctor and refreshes when linked records change.'}</p>
      {modelText && analysis?.affiliation_summary ? <p className="mt-2 text-sm text-muted">{analysis.affiliation_summary}</p> : null}
      <p className="mt-2 text-xs text-muted">
        {modelText
          ? "Written from this doctor's stored evidence. It is rewritten when a new record is added or a field changes."
          : 'Built from the stored profile. The chat model replaces this text when its run finishes.'}
      </p>
    </section>
  );
}

function KnownValues({ doctorId }: { doctorId: string }) {
  const query = useQuery({
    queryKey: ['known-values', doctorId],
    queryFn: ({ signal }) => apiFetch<{ items: Array<Record<string, unknown>> }>(`/doctors/${doctorId}/known-values`, { signal }),
  });
  if (query.isLoading) return <Skeleton className="h-40 w-full" />;
  if (query.isError) return <ErrorState message={(query.error as Error).message} onRetry={() => query.refetch()} />;
  const items = query.data?.items || [];
  return (
    <table className="w-full text-sm">
      <thead className="text-left text-xs text-muted">
        <tr>
          <th className="py-1">Value</th>
          <th>Kind</th>
          <th>Round</th>
          <th>Source</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item, index) => (
          <tr key={`${item.field}-${index}`} className="border-t border-border">
            <td className="py-1 pr-2">{String(item.value || '')}</td>
            <td className="pr-2">{String(item.kind || '')}</td>
            <td className="pr-2 tabular-nums">{String(item.round ?? '')}</td>
            <td className="pr-2">{String(item.source || '')}</td>
            <td>{String(item.status || '')}</td>
          </tr>
        ))}
        {items.length === 0 ? (
          <tr>
            <td className="py-3 text-muted" colSpan={5}>
              No learned values yet.
            </td>
          </tr>
        ) : null}
      </tbody>
    </table>
  );
}

function LineageGraph({ doctorId }: { doctorId: string }) {
  const [round, setRound] = useState('');
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const query = useQuery({
    queryKey: ['lineage', doctorId],
    queryFn: ({ signal }) =>
      apiFetch<{ nodes: Array<Record<string, unknown>>; edges: Array<Record<string, unknown>> }>(`/doctors/${doctorId}/lineage`, { signal }),
  });
  if (query.isLoading) return <Skeleton className="h-40 w-full" />;
  if (query.isError) return <ErrorState message={(query.error as Error).message} onRetry={() => query.refetch()} />;
  const nodes = (query.data?.nodes || []).filter((node) => round === '' || node.kind !== 'record' || String(node.round ?? '') === round);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor="round-filter">Round</label>
        <select id="round-filter" className="rounded-md border border-border px-2 py-1" value={round} onChange={(event) => setRound(event.target.value)}>
          <option value="">All rounds</option>
          <option value="0">Round 0</option>
          <option value="1">Round 1</option>
          <option value="2">Round 2</option>
        </select>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2" aria-label="Lineage graph">
        {nodes.map((node) => (
          <button
            key={String(node.id)}
            type="button"
            className="min-w-36 rounded-md border border-border bg-white px-3 py-2 text-left text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
            onClick={() => setSelected(node)}
          >
            <div className="text-xs uppercase text-muted">{String(node.kind)}</div>
            <div className="font-medium">{String(node.label)}</div>
            <div className="text-xs text-muted">{String(node.status || '')}</div>
          </button>
        ))}
      </div>
      {selected ? (
        <div className="rounded-md border border-border bg-slate-50 p-3 text-sm" role="region" aria-label="Lineage detail">
          <div className="font-semibold">{String(selected.label)}</div>
          <p className="mt-1">Status: {String(selected.status || '')}</p>
          <p>Round: {String(selected.round ?? '')}</p>
          <p>Found by: {Array.isArray(selected.found_by) ? selected.found_by.join(', ') : String(selected.route || '')}</p>
          <p>Score: {String(selected.score ?? selected.splink_score ?? '')}</p>
          <p>{String(selected.reason || '')}</p>
        </div>
      ) : null}
      <details>
        <summary className="cursor-pointer text-sm">Table view</summary>
        <table className="mt-2 w-full text-sm">
          <thead className="text-left text-xs text-muted">
            <tr>
              <th>Node</th>
              <th>Kind</th>
              <th>Status</th>
              <th>Round</th>
            </tr>
          </thead>
          <tbody>
            {nodes.map((node) => (
              <tr key={`row-${node.id}`} className="border-t border-border">
                <td className="py-1">{String(node.label)}</td>
                <td>{String(node.kind)}</td>
                <td>{String(node.status || '')}</td>
                <td>{String(node.round ?? '')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

function PrescriberImpact({
  records,
}: {
  records: Array<{ source_id: string; provider_identifier?: string | null }>;
}) {
  const claims = records.filter((row) => row.source_id === 'claims');
  const byStated = new Map<string, number>();
  claims.forEach((row) => {
    const key = row.provider_identifier || 'No NPI on the claim';
    byStated.set(key, (byStated.get(key) || 0) + 1);
  });
  return (
    <div className="space-y-2 text-sm">
      <p>{claims.length ? `${claims.length} claims are attributed to this doctor after cleanup.` : 'No claims are linked to this doctor.'}</p>
      {byStated.size > 1 ? <p>Previously split across {byStated.size} stated prescriber values.</p> : null}
      <ul className="space-y-1">
        {[...byStated.entries()].map(([stated, count]) => (
          <li key={stated}>
            {count} arrived under {stated}
          </li>
        ))}
      </ul>
    </div>
  );
}

function PaymentsList({
  records,
}: {
  records: Array<{ source_record_id: string; recorded_name?: string | null; provider_identifier?: string | null; resolution_status?: string | null }>;
}) {
  if (!records.length) return <p className="text-sm text-muted">No payments are linked to this doctor.</p>;
  return (
    <ul className="space-y-2 text-sm">
      {records.map((row) => {
        const readiness = !row.provider_identifier
          ? 'Missing NPI'
          : row.resolution_status === 'pending_review'
            ? 'Needs compliance review'
            : 'Ready to report';
        return (
          <li key={row.source_record_id} className="rounded-md border border-border p-3">
            <div className="font-medium">{row.recorded_name || row.source_record_id}</div>
            <div className="text-xs text-muted">NPI {row.provider_identifier || 'not on the payment'} · {readiness}</div>
          </li>
        );
      })}
    </ul>
  );
}

function SimilarRecords({ doctorId }: { doctorId: string }) {
  const query = useQuery({
    queryKey: ['similar', doctorId],
    queryFn: ({ signal }) => apiFetch<{ doctors: Array<Record<string, unknown>> }>(`/doctors/${doctorId}/similar`, { signal }),
  });
  if (query.isLoading) return <Skeleton className="h-24 w-full" />;
  if (query.isError) return <ErrorState message={(query.error as Error).message} onRetry={() => query.refetch()} />;
  const doctors = query.data?.doctors || [];
  if (!doctors.length) return <p className="text-sm text-muted">No same-name doctor is kept separate from this record.</p>;
  return (
    <ul className="space-y-2">
      {doctors.map((doctor) => (
        <li key={String(doctor.doctor_id)} className="rounded-md border border-border p-3 text-sm">
          <div className="font-medium">{String(doctor.name)}</div>
          <p className="text-muted">NPI {String(doctor.npi || '')} · {String(doctor.location || '')}</p>
          <p>{String(doctor.reason || '')}</p>
        </li>
      ))}
    </ul>
  );
}
