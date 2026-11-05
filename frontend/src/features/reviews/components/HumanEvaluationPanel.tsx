import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import type { ReviewDetail } from '../../../api/contracts';
import { saveReviewAssignment } from '../../../api/reviews';
import { ErrorState } from '../../../components/ErrorState';
import { displayValue } from '../../../utils/formatters';

export function HumanEvaluationPanel({ review }: { review: ReviewDetail }) {
  const queryClient = useQueryClient();
  const [comment, setComment] = useState(review.assignment_comment || '');
  const [error, setError] = useState<string | null>(null);
  const assigned = review.assignment_status === 'assigned_for_human_review';

  const mutation = useMutation({
    mutationFn: (assign: boolean) =>
      saveReviewAssignment(review.review_id, {
        assign,
        assigned_reviewer: assign ? 'Steward' : null,
        assignment_comment: comment || null,
        expected_version: review.version,
      }),
    onSuccess: async () => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ['review', review.review_id] });
      await queryClient.invalidateQueries({ queryKey: ['reviews'] });
    },
    onError: (err) => setError((err as Error).message),
  });

  return (
    <section className="space-y-3 rounded-[12px] border border-border bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold">Human evaluation</h3>
      <p className="text-sm text-muted">
        Cases stay <strong>Unassigned</strong> unless a real steward claims them. No fictional reviewer names are invented.
      </p>
      <dl className="grid gap-2 text-sm md:grid-cols-3">
        <div>
          <dt className="text-muted">Status</dt>
          <dd className="font-medium">{displayValue(review.assignment_status, 'unassigned')}</dd>
        </div>
        <div>
          <dt className="text-muted">Reviewer</dt>
          <dd className="font-medium">{displayValue(review.assigned_reviewer, 'Unassigned')}</dd>
        </div>
        <div>
          <dt className="text-muted">Assigned at</dt>
          <dd className="font-medium">{displayValue(review.assigned_at, '—')}</dd>
        </div>
      </dl>
      <label className="block text-sm">
        <span className="text-muted">Assignment note</span>
        <textarea className="mt-1 w-full rounded-md border border-border p-2 text-sm" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} />
      </label>
      {error ? <ErrorState title="Assignment failed" message={error} /> : null}
      <div className="flex gap-2">
        <button
          type="button"
          className="rounded-md bg-primary px-3 py-2 text-sm text-white disabled:opacity-50"
          disabled={mutation.isPending || assigned}
          onClick={() => mutation.mutate(true)}
        >
          Claim for review
        </button>
        <button
          type="button"
          className="rounded-md border border-border px-3 py-2 text-sm disabled:opacity-50"
          disabled={mutation.isPending || !assigned}
          onClick={() => mutation.mutate(false)}
        >
          Return to unassigned
        </button>
      </div>
    </section>
  );
}
