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
          </div>
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

      <ReviewComparison comparison={review.comparison} />
      <RecommendationPanel recommendation={review.recommendation} />
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-md border border-border px-3 py-2 text-sm disabled:opacity-50"
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
          Explain review case
        </button>
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
