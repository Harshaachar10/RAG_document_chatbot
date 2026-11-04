import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { startChangeExtraction, startIdentityAnalysis } from '../api/ai';
import { fetchSourceRecords, fetchSources } from '../api/sources';
import { ErrorState } from '../components/ErrorState';
import { FilterBar, FilterField, inputClass } from '../components/FilterBar';
import { Skeleton } from '../components/Skeleton';
import { AiResultCard } from '../features/ai/AiResultCard';
import { useAiJob } from '../features/ai/useAiJob';
import { EvidenceWorkspace } from '../features/doctors/components/EvidenceWorkspace';
import { ProcessingReplay } from '../features/sources/components/ProcessingReplay';
import { SourceCards } from '../features/sources/components/SourceCards';
import { SourceRecordsTable } from '../features/sources/components/SourceRecordsTable';
import { useUrlState } from '../hooks/useUrlState';

export function SourcesPage() {
  const { get, setMany } = useUrlState();
  const tab = get('tab', 'records');
  const sourceId = get('source_id');
  const status = get('status');
  const search = get('search');
  const page = Number(get('page', '1'));
  const queryClient = useQueryClient();
  const [picked, setPicked] = useState<string[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const ai = useAiJob('sources-analysis');
  const selectedSet = new Set(picked);

  async function runAnalysis(kind: 'identity' | 'changes', forceRefresh = false) {
    setActionError(null);
    setSubmitting(true);
    try {
      const job = kind === 'identity'
        ? await startIdentityAnalysis(picked, forceRefresh)
        : await startChangeExtraction(picked, forceRefresh);
      ai.setJobId(job.job_id);
      await queryClient.invalidateQueries({ queryKey: ['ai-jobs'] });
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  const sourcesQuery = useQuery({
    queryKey: ['sources'],
    queryFn: ({ signal }) => fetchSources(signal),
  });

  const selected = sourceId || sourcesQuery.data?.items[0]?.source_id || '';

  useEffect(() => {
    if (ai.job?.status === 'completed') {
      queryClient.invalidateQueries({ queryKey: ['reviews'] });
      queryClient.invalidateQueries({ queryKey: ['ai-jobs'] });
    }
  }, [ai.job?.status, ai.job?.analysis_id, queryClient]);

  const recordsQuery = useQuery({
    queryKey: ['source-records', selected, status, search, page],
    queryFn: ({ signal }) =>
      fetchSourceRecords(selected, { status, search, page, page_size: 25 }, signal),
    enabled: !!selected && tab !== 'processing',
  });

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Sources & Processing</h1>
        <p className="mt-1 text-sm text-muted">
          Source snapshots from the supplied dataset. The processing tab replays a prepared demo. Live analysis runs only when you select records.
        </p>
      </header>

      <div className="flex gap-2">
        <button
          type="button"
          className={`rounded-md px-3 py-1.5 text-sm ${tab === 'records' ? 'bg-primary text-white' : 'bg-slate-100'}`}
          onClick={() => setMany({ tab: 'records' })}
        >
          Source Records
        </button>
        <button
          type="button"
          className={`rounded-md px-3 py-1.5 text-sm ${tab === 'processing' ? 'bg-primary text-white' : 'bg-slate-100'}`}
          onClick={() => setMany({ tab: 'processing' })}
        >
          Processing Demo
        </button>
      </div>

      {tab === 'processing' ? (
        <ProcessingReplay />
      ) : (
        <>
          {sourcesQuery.isLoading ? <Skeleton className="h-32 w-full" /> : null}
          {sourcesQuery.isError ? (
            <ErrorState message={(sourcesQuery.error as Error).message} onRetry={() => sourcesQuery.refetch()} />
          ) : null}
          {sourcesQuery.data ? (
            <SourceCards
              sources={sourcesQuery.data.items}
              selectedId={selected}
              onSelect={(id) => setMany({ source_id: id, page: '1' })}
            />
          ) : null}

          <FilterBar>
            <FilterField label="Search">
              <input className={inputClass} value={search} onChange={(e) => setMany({ search: e.target.value, page: '1' })} />
            </FilterField>
            <FilterField label="Status">
              <select className={inputClass} value={status} onChange={(e) => setMany({ status: e.target.value, page: '1' })}>
                <option value="">All</option>
                <option value="linked">Linked</option>
                <option value="review_required">Review required</option>
                <option value="unresolved">Unresolved</option>
                <option value="identifier_conflict">Identifier conflict</option>
                <option value="duplicate_ingestion">Duplicate ingestion</option>
              </select>
            </FilterField>
          </FilterBar>

          {recordsQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
          {recordsQuery.isError ? (
            <ErrorState message={(recordsQuery.error as Error).message} onRetry={() => recordsQuery.refetch()} />
          ) : null}
          {recordsQuery.data ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                  disabled={submitting || ai.busy || picked.length < 2}
                  onClick={() => runAnalysis('identity')}
                >
                  Analyze selected records
                </button>
                <button
                  type="button"
                  className="rounded-md border border-border px-3 py-2 text-sm disabled:opacity-50"
                  disabled={submitting || ai.busy || picked.length < 1}
                  onClick={() => runAnalysis('changes')}
                >
                  Analyze changes in selected evidence
                </button>
                <span className="text-xs text-muted">{picked.length} selected</span>
              </div>
              {actionError ? <ErrorState title="Analysis failed" message={actionError} /> : null}
              <AiResultCard
                job={ai.job}
                onOpenEvidence={setEvidenceId}
                refreshDisabled={submitting || ai.busy || picked.length < 2}
                onRefresh={() => runAnalysis('identity', true)}
              />
              {evidenceId ? <EvidenceWorkspace evidenceId={evidenceId} /> : null}
              <SourceRecordsTable
                rows={recordsQuery.data.items}
                selectedIds={selectedSet}
                onToggle={(id) => setPicked((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])}
              />
              <div className="flex justify-between text-sm">
                <span className="text-muted">{recordsQuery.data.total} records</span>
                <div className="flex gap-2">
                  <button type="button" className="rounded-md border px-3 py-1.5" disabled={page <= 1} onClick={() => setMany({ page: String(page - 1) })}>Previous</button>
                  <button type="button" className="rounded-md border px-3 py-1.5" disabled={page * 25 >= recordsQuery.data.total} onClick={() => setMany({ page: String(page + 1) })}>Next</button>
                </div>
              </div>
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
