import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { startReviewExplanation } from '../api/ai';
import { fetchReview, submitDecision } from '../api/reviews';
import { ErrorState } from '../components/ErrorState';
import { Skeleton } from '../components/Skeleton';
import { StatusBadge } from '../components/StatusBadge';
import { AiResultCard } from '../features/ai/AiResultCard';
import { useAiJob } from '../features/ai/useAiJob';
import { EvidenceWorkspace } from '../features/doctors/components/EvidenceWorkspace';
import { DecisionDialog } from '../features/reviews/components/DecisionDialog';
import { HumanEvaluationPanel } from '../features/reviews/components/HumanEvaluationPanel';
import { PipelineMatchPanel } from '../features/reviews/components/PipelineMatchPanel';
import { RecommendationPanel } from '../features/reviews/components/RecommendationPanel';
import { ReviewComparison } from '../features/reviews/components/ReviewComparison';
import { displayValue } from '../utils/formatters';

function newIdempotencyKey() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `idem-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function ReviewDetailPage() {
  const { reviewId = '' } = useParams();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [explainError, setExplainError] = useState<string | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<'case' | 'ai' | 'human'>('case');
  const ai = useAiJob(`review:${reviewId}`);

  const detailQuery = useQuery({
    queryKey: ['review', reviewId],
    queryFn: ({ signal }) => fetchReview(reviewId, signal),
  });

  const mutation = useMutation({
    mutationFn: (payload: { action: string; decision: string; selected_doctor_id?: string; comment: string }) =>
      submitDecision(reviewId, {
        ...payload,
        expected_version: detailQuery.data!.version,
        idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: async () => {
      setDialogOpen(false);
      setToast('Decision saved.');
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['review', reviewId] }),
        queryClient.invalidateQueries({ queryKey: ['reviews'] }),
        queryClient.invalidateQueries({ queryKey: ['doctors'] }),
        queryClient.invalidateQueries({ queryKey: ['doctor'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] }),
        queryClient.invalidateQueries({ queryKey: ['activity'] }),
        queryClient.invalidateQueries({ queryKey: ['sources'] }),
      ]);
    },
  });

  if (detailQuery.isLoading) return <Skeleton className="h-80 w-full" />;
  if (detailQuery.isError) {
    return <ErrorState message={(detailQuery.error as Error).message} onRetry={() => detailQuery.refetch()} />;
  }
  const review = detailQuery.data!;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs text-muted"><Link to="/reviews" className="text-primary hover:underline">Reviews</Link> / {review.review_id}</p>
          <h1 className="mt-1 text-2xl font-semibold">{review.title}</h1>
          <div className="mt-2 flex flex-wrap gap-2">
            <StatusBadge value={review.status} kind="review" />
            <StatusBadge value={review.severity} kind="severity" />
            <span className="text-sm text-muted">{review.case_type}</span>
            {review.assignment_status === 'assigned_for_human_review' ? (
              <span className="rounded-md bg-sky-50 px-2 py-0.5 text-sm text-sky-900">
                Assigned to {displayValue(review.assigned_reviewer)}
              </span>
            ) : null}
          </div>
          {review.doctor_id ? (
            <p className="mt-2 text-sm text-muted">
              Doctor{' '}
              <Link className="text-primary hover:underline" to={`/golden-records?doctor_id=${review.doctor_id}&tab=summary`}>
                {review.doctor_id}
              </Link>
              {review.source_record_id ? ` · Source ${review.source_record_id}` : ''}
            </p>
          ) : null}
        </div>
        {review.valid_actions.length ? (
          <button
            type="button"
            className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white"
            onClick={() => setDialogOpen(true)}
          >
            Decide
          </button>
        ) : (
          <span className="text-sm text-muted">No further actions available</span>
        )}
      </header>

      {toast ? <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900" role="status">{toast}</div> : null}
      {mutation.isError ? (
        <ErrorState title="Decision failed" message={(mutation.error as Error).message} />
      ) : null}

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Review detail sections">
        {[
          { id: 'case', label: 'Case & conflicts' },
          { id: 'ai', label: 'AI reasoning' },
          { id: 'human', label: 'Human Evaluation' },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={detailTab === tab.id}
            className={`rounded-md px-3 py-1.5 text-sm ${detailTab === tab.id ? 'bg-primary text-white' : 'bg-slate-100'}`}
            onClick={() => setDetailTab(tab.id as typeof detailTab)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {detailTab === 'case' ? (
        <div className="space-y-4">
          <PipelineMatchPanel
            pipelineAction={review.pipeline_action}
            pipelineReason={review.pipeline_reason}
            pipelineScore={review.pipeline_score}
            queue={review.queue}
            recordFlags={review.record_flags}
            candidates={review.candidates as never}
          />
          <ReviewComparison
            comparison={review.comparison}
            caseTitle={review.title}
            doctorId={review.doctor_id}
            onOpenEvidence={setEvidenceId}
          />
          <RecommendationPanel recommendation={review.recommendation} />
          <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold">Proposed impact</h3>
            <p className="mt-2 text-sm">
              Field: {displayValue(review.proposed_field)} → {displayValue(review.proposed_value)}
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
              {((review.impact.action_effects as string[]) || []).map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </section>
          <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold">Cited evidence</h3>
            <ul className="mt-2 space-y-1 text-sm">
              {review.evidence.map((e) => (
                <li key={String(e.evidence_id)}>
                  <button type="button" className="text-primary hover:underline" onClick={() => setEvidenceId(String(e.evidence_id))}>
                    {displayValue(e.citation_label || e.evidence_id)}
                  </button>
                  {' '}— “{displayValue(e.quoted_text)}”
                </li>
              ))}
              {!review.evidence.length ? <li className="text-muted">No linked evidence rows</li> : null}
            </ul>
          </section>
          {evidenceId ? <EvidenceWorkspace evidenceId={evidenceId} /> : null}
        </div>
      ) : null}

      {detailTab === 'ai' ? (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              disabled={explaining || ai.busy}
              onClick={async () => {
                setExplainError(null);
                setExplaining(true);
                try {
                  const job = await startReviewExplanation(reviewId, false);
                  ai.setJobId(job.job_id);
                } catch (err) {
                  setExplainError((err as Error).message);
                } finally {
                  setExplaining(false);
                }
              }}
            >
              Generate AI reasoning
            </button>
            <p className="self-center text-xs text-muted">
              Explains supported facts, proposed changes, and unresolved conflicts using this case and its evidence history.
            </p>
          </div>
          {explainError ? <ErrorState title="Explanation failed" message={explainError} /> : null}
          <AiResultCard
            job={ai.job}
            onOpenEvidence={setEvidenceId}
            refreshDisabled={explaining || ai.busy}
            onRefresh={async () => {
              setExplaining(true);
              try {
                const job = await startReviewExplanation(reviewId, true);
                ai.setJobId(job.job_id);
              } catch (err) {
                setExplainError((err as Error).message);
              } finally {
                setExplaining(false);
              }
            }}
          />
          {evidenceId ? <EvidenceWorkspace evidenceId={evidenceId} /> : null}
        </div>
      ) : null}

      {detailTab === 'human' ? <HumanEvaluationPanel review={review} /> : null}

      <DecisionDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        actions={review.valid_actions}
        candidates={
          review.candidates.length
            ? review.candidates
            : review.doctor_id
              ? [{ candidate_doctor_id: review.doctor_id, doctor_name: review.doctor_id }]
              : []
        }
        submitting={mutation.isPending}
        onSubmit={(payload) => mutation.mutate(payload)}
      />
    </div>
  );
}
