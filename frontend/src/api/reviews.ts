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
