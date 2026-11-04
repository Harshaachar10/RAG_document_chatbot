import { useQuery, useQueryClient } from '@tanstack/react-query';
import * as Tabs from '@radix-ui/react-tabs';
import { Expand, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useMemo, useState } from 'react';
import { fetchAiAnalyses, fetchProfileSummary, startProfileSummary } from '../../../api/ai';
import {
  fetchDoctor,
  fetchDoctorHistory,
  fetchDoctorReviewHistory,
  fetchDoctorSourceRecords,
  fetchMatchExplanation,
} from '../../../api/doctors';
import { AiResultCard } from '../../ai/AiResultCard';
import { useAiJob } from '../../ai/useAiJob';
import { ErrorState } from '../../../components/ErrorState';
import { Skeleton } from '../../../components/Skeleton';
import { StatusBadge } from '../../../components/StatusBadge';
import { displayValue } from '../../../utils/formatters';
import { DoctorTimeline, FieldHistoryTable } from './DoctorTimeline';
import { EvidenceWorkspace } from './EvidenceWorkspace';
import { LinkedRecordsTable } from './LinkedRecordsTable';
import { MatchExplanation } from './MatchExplanation';
import { ProfileSummary } from './ProfileSummary';
import { ReviewHistory } from './ReviewHistory';

const TABS = [
  { id: 'summary', label: 'Profile Summary' },
  { id: 'linked', label: 'Linked Records' },
  { id: 'history', label: 'History & Timeline' },
  { id: 'evidence', label: 'Evidence & Sources' },
  { id: 'match', label: 'Why These Records Match' },
  { id: 'reviews', label: 'Review History' },
] as const;

export function DoctorProfile({
  doctorId,
  tab = 'summary',
  onTabChange,
  mode = 'page',
  onClose,
  expandTo,
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
  const [aliasFilter, setAliasFilter] = useState<string | null>(null);
  const [historyMode, setHistoryMode] = useState<'timeline' | 'table'>('timeline');
  const [evidenceId, setEvidenceId] = useState<string | null>(initialEvidenceId || null);
  const [mobileEvidence, setMobileEvidence] = useState(false);

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
  const reviewHistoryQuery = useQuery({
    queryKey: ['doctor-review-history', doctorId],
    queryFn: ({ signal }) => fetchDoctorReviewHistory(doctorId, signal),
  });

  const evidenceList = useMemo(() => {
    const ids = new Set<string>();
    (recordsQuery.data?.items || []).forEach((r) => r.evidence_ids.forEach((id) => ids.add(id)));
    (historyQuery.data?.items || []).forEach((e) => {
      if (e.evidence_id) ids.add(e.evidence_id);
    });
    return Array.from(ids);
  }, [recordsQuery.data, historyQuery.data]);

  const openEvidence = (id: string) => {
    setEvidenceId(id);
    setMobileEvidence(true);
    onTabChange?.('evidence');
  };

  if (doctorQuery.isLoading) return <Skeleton className="h-96 w-full" />;
  if (doctorQuery.isError) {
    return <ErrorState message={(doctorQuery.error as Error).message} onRetry={() => doctorQuery.refetch()} />;
  }
  const doctor = doctorQuery.data!;

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
              <span className="text-muted">NPI: Not verified</span>
              <StatusBadge value={doctor.identity_review_status === 'pending' ? 'pending' : 'clear'} kind="review" />
              {doctor.pending_field_changes > 0 ? (
                <StatusBadge value="pending" kind="review" />
              ) : null}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="text-xs text-muted self-center">Also recorded as:</span>
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
            {mode === 'drawer' && expandTo ? (
              <Link
                to={expandTo}
                className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-sm hover:bg-slate-50"
              >
                <Expand size={14} /> Expand profile
              </Link>
            ) : null}
            {mode === 'drawer' && onClose ? (
              <button type="button" onClick={onClose} className="rounded-md p-1.5 hover:bg-slate-100" aria-label="Close">
                <X size={16} />
              </button>
            ) : null}
          </div>
        </div>
      </header>

      <Tabs.Root
        value={tab}
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
                onOpenEvidence={openEvidence}
                aliasFilter={aliasFilter}
              />
            ) : null}
          </Tabs.Content>
          <Tabs.Content value="history">
            <div className="mb-3 flex gap-2">
              <button type="button" className={`rounded-md px-2.5 py-1 text-xs ${historyMode === 'timeline' ? 'bg-primary text-white' : 'bg-slate-100'}`} onClick={() => setHistoryMode('timeline')}>Timeline</button>
              <button type="button" className={`rounded-md px-2.5 py-1 text-xs ${historyMode === 'table' ? 'bg-primary text-white' : 'bg-slate-100'}`} onClick={() => setHistoryMode('table')}>Table</button>
            </div>
            {historyQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
            {historyQuery.data ? (
              historyMode === 'timeline' ? (
                <DoctorTimeline events={historyQuery.data.items} highlightEventId={eventId} onOpenEvidence={openEvidence} />
              ) : (
                <FieldHistoryTable events={historyQuery.data.items} highlightEventId={eventId} onOpenEvidence={openEvidence} />
              )
            ) : null}
          </Tabs.Content>
          <Tabs.Content value="evidence">
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
          </Tabs.Content>
          <Tabs.Content value="match">
            {matchQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
            {matchQuery.data ? <MatchExplanation data={matchQuery.data} /> : null}
          </Tabs.Content>
          <Tabs.Content value="reviews">
            {reviewHistoryQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
            {reviewHistoryQuery.data ? <ReviewHistory items={reviewHistoryQuery.data.items} /> : null}
          </Tabs.Content>
        </div>
      </Tabs.Root>
    </div>
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
          Generate AI summary
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
        The profile above is the prepared record. A summary is generated only when you ask for it.
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
