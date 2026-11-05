import { useQuery, useQueryClient } from '@tanstack/react-query';
import * as Tabs from '@radix-ui/react-tabs';
import { X } from 'lucide-react';
import { useMemo, useState } from 'react';
import {
  fetchAiAnalyses,
  fetchProfileSummary,
  startChangeExtraction,
  startIdentityAnalysis,
  startProfileSummary,
} from '../../../api/ai';
import {
  fetchDoctor,
  fetchDoctorHistory,
  fetchDoctorSourceRecords,
  fetchMatchExplanation,
} from '../../../api/doctors';
import { AiResultCard } from '../../ai/AiResultCard';
import { useAiJob } from '../../ai/useAiJob';
import { ErrorState } from '../../../components/ErrorState';
import { Skeleton } from '../../../components/Skeleton';
import { StatusBadge } from '../../../components/StatusBadge';
import { displayValue } from '../../../utils/formatters';
import { DoctorTimeline } from './DoctorTimeline';
import { EvidenceWorkspace } from './EvidenceWorkspace';
import { LinkedRecordsTable } from './LinkedRecordsTable';
import { MatchExplanation } from './MatchExplanation';
import { ProfileSummary } from './ProfileSummary';

const TABS = [
  { id: 'summary', label: 'Overview' },
  { id: 'linked', label: 'Linked Records' },
  { id: 'history', label: 'Timeline' },
  { id: 'evidence', label: 'Evidence / AI Reasoning' },
] as const;

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
  const activeTab = tab === 'match' || tab === 'reviews' ? 'evidence' : tab;
  const [aliasFilter, setAliasFilter] = useState<string | null>(null);
  const [evidenceId, setEvidenceId] = useState<string | null>(initialEvidenceId || null);
  const [mobileEvidence, setMobileEvidence] = useState(false);
  const [highlightGapsFor, setHighlightGapsFor] = useState<string | null>(null);

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
              {displayValue(doctor.specialty)} · {[doctor.city, doctor.state].filter(Boolean).join(', ') || 'Location not available'}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              <span className="rounded-md bg-slate-100 px-2 py-0.5 font-medium">{doctor.doctor_id}</span>
              <span className="text-muted">NPI reference: {displayValue(doctor.mock_npi_ref, 'Not verified')}</span>
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
          </div>
          <div className="flex items-center gap-2">
            {mode === 'drawer' && onClose ? (
              <button type="button" onClick={onClose} className="rounded-md p-1.5 hover:bg-slate-100" aria-label="Close">
                <X size={16} />
              </button>
            ) : null}
          </div>
        </div>
      </header>

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
              className="rounded-md px-3 py-1.5 text-sm data-[state=active]:bg-white data-[state=active]:font-semibold data-[state=active]:shadow-sm"
            >
              {t.label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <div className="min-h-0 flex-1 overflow-auto p-4">
          <Tabs.Content value="summary">
            <div className="space-y-4">
              <ProfileSummary doctor={doctor} onViewEvidence={() => onTabChange?.('evidence')} />
              <ProfileAiPanel doctorId={doctorId} onOpenEvidence={openEvidence} />
            </div>
          </Tabs.Content>
          <Tabs.Content value="linked">
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
                  else {
                    setHighlightGapsFor(rec.source_record_id);
                    onTabChange?.('evidence');
                  }
                }}
                aliasFilter={aliasFilter}
              />
            ) : null}
          </Tabs.Content>
          <Tabs.Content value="history">
            <HistoryAiPanel
              recordIds={(recordsQuery.data?.items || []).map((r) => r.source_record_id)}
              onOpenEvidence={openEvidence}
            />
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
              <MatchAiPanel
                recordIds={(recordsQuery.data?.items || []).map((r) => r.source_record_id)}
                onOpenEvidence={openEvidence}
              />
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
    </div>
  );
}

function HistoryAiPanel({
  recordIds,
  onOpenEvidence,
}: {
  recordIds: string[];
  onOpenEvidence: (id: string) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const ai = useAiJob(`history-changes:${recordIds.slice(0, 8).join(',')}`);

  async function generate(forceRefresh: boolean) {
    if (!recordIds.length) {
      setError('No linked source records are available for AI trail analysis.');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const job = await startChangeExtraction(recordIds.slice(0, 8), forceRefresh);
      ai.setJobId(job.job_id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mb-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          disabled={submitting || ai.busy || !recordIds.length}
          onClick={() => generate(false)}
        >
          Summarize identity trail with AI
        </button>
        <p className="text-xs text-muted">
          Uses current linked documents and dated history. Supported facts, proposed changes, and unresolved gaps stay separate.
        </p>
      </div>
      {error ? <ErrorState title="Trail analysis failed" message={error} /> : null}
      {ai.job ? (
        <AiResultCard
          job={ai.job}
          onOpenEvidence={onOpenEvidence}
          onRefresh={() => generate(true)}
          refreshDisabled={submitting || ai.busy}
        />
      ) : null}
    </section>
  );
}

function MatchAiPanel({
  recordIds,
  onOpenEvidence,
}: {
  recordIds: string[];
  onOpenEvidence: (id: string) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const ai = useAiJob(`match-identity:${recordIds.slice(0, 8).join(',')}`);

  async function generate(forceRefresh: boolean) {
    if (recordIds.length < 2) {
      setError('At least two linked source records are needed for AI identity reasoning.');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const job = await startIdentityAnalysis(recordIds.slice(0, 8), forceRefresh);
      ai.setJobId(job.job_id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mb-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          disabled={submitting || ai.busy || recordIds.length < 2}
          onClick={() => generate(false)}
        >
          Explain why these records may match
        </button>
        <p className="text-xs text-muted">
          Azure OpenAI cites shared identifiers, credentials, contacts, aliases, and dated evidence without claiming a confirmed match when gaps remain.
        </p>
      </div>
      {error ? <ErrorState title="Identity analysis failed" message={error} /> : null}
      {ai.job ? (
        <AiResultCard
          job={ai.job}
          onOpenEvidence={onOpenEvidence}
          onRefresh={() => generate(true)}
          refreshDisabled={submitting || ai.busy}
        />
      ) : null}
    </section>
  );
}

function ProfileAiPanel({
  doctorId,
  onOpenEvidence,
}: {
  doctorId: string;
  onOpenEvidence: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const ai = useAiJob(`summary:${doctorId}`);
  const cached = useQuery({
    queryKey: ['doctor-ai-summary', doctorId],
    queryFn: ({ signal }) => fetchProfileSummary(doctorId, signal),
  });
  const history = useQuery({
    queryKey: ['ai-history', doctorId],
    queryFn: ({ signal }) => fetchAiAnalyses({ doctor_id: doctorId }, signal),
    enabled: showHistory,
  });

  async function generate(forceRefresh: boolean) {
    setError(null);
    setSubmitting(true);
    try {
      const job = await startProfileSummary(doctorId, forceRefresh);
      ai.setJobId(job.job_id);
      await queryClient.invalidateQueries({ queryKey: ['doctor-ai-summary', doctorId] });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  const job = ai.job || (cached.data?.analysis
    ? {
        job_id: cached.data.analysis.analysis_id,
        status: 'completed',
        status_url: '',
        cached: true,
        analysis: cached.data.analysis,
      }
    : null);

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          disabled={submitting || ai.busy}
          onClick={() => generate(false)}
        >
          Generate AI overview
        </button>
        <button
          type="button"
          className="rounded-md border border-border px-3 py-2 text-sm disabled:opacity-50"
          onClick={() => setShowHistory((value) => !value)}
        >
          Open analysis history
        </button>
      </div>
      <p className="text-xs text-muted">
        Summarizes current profile facts and remaining gaps from the linked evidence history.
      </p>
      {cached.isError ? <ErrorState message={(cached.error as Error).message} onRetry={() => cached.refetch()} /> : null}
      {error ? <ErrorState title="Summary failed" message={error} /> : null}
      {job ? (
        <AiResultCard
          job={job}
          onOpenEvidence={onOpenEvidence}
          onRefresh={() => generate(true)}
          refreshDisabled={submitting || ai.busy}
        />
      ) : null}
      {showHistory && history.data ? (
        <ul className="space-y-1 text-sm">
          {history.data.items.map((item) => (
            <li key={item.analysis_id} className="rounded-md border border-border px-3 py-2">
              {item.operation} · {item.label || item.outcome} · {item.completed_at || 'in progress'}
            </li>
          ))}
          {!history.data.items.length ? <li className="text-muted">No saved analyses for this profile.</li> : null}
        </ul>
      ) : null}
    </section>
  );
}
