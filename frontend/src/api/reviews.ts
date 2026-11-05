import { apiFetch, toQuery } from './client';
import type { DecisionRequest, DecisionResponse, Paginated, ReviewDetail, ReviewListItem } from './contracts';

export function fetchReviews(params: Record<string, unknown>, signal?: AbortSignal) {
  return apiFetch<Paginated<ReviewListItem>>(`/reviews${toQuery(params)}`, { signal });
}

export function fetchReview(reviewId: string, signal?: AbortSignal) {
  return apiFetch<ReviewDetail>(`/reviews/${reviewId}`, { signal });
}

export function submitDecision(reviewId: string, body: DecisionRequest) {
  return apiFetch<DecisionResponse>(`/reviews/${reviewId}/decisions`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function saveReviewAssignment(
  reviewId: string,
  body: {
    assign: boolean;
    assigned_reviewer?: string | null;
    assignment_comment?: string | null;
    expected_version: number;
  },
) {
  return apiFetch<{ review: ReviewDetail; snapshot_version: number; audit_id: string }>(
    `/reviews/${reviewId}/assignment`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
  );
}
