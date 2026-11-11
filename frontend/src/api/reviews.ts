import { apiFetch, toQuery } from './client';
import type { DecisionRequest, DecisionResponse, Paginated, ReviewDetail, ReviewListItem } from './contracts';

export type ReviewBoard = {
  needs_run: boolean;
  waiting: number;
  subtitle: string;
  counts: Record<string, number>;
  items: ReviewCase[];
};

export type ReviewCase = {
  id: string;
  review_id?: string | null;
  record_id: string;
  queue_type: 'compliance' | 'safety' | 'identity' | 'proposed' | 'unmatched';
  risk: string;
  risk_tone: string;
  type_label: string;
  question: string;
  source_label: string;
  amount?: number | null;
  doctor_id?: string | null;
  doctor_name?: string | null;
  doctor_city?: string | null;
  case_type?: string | null;
  version: number;
  link_action?: string | null;
  link_blocked?: boolean;
  pipeline_reason?: string | null;
  record: {
    source?: string;
    name?: string | null;
    npi?: string | null;
    npi_label?: string | null;
    specialty?: string | null;
    practice?: string | null;
    city?: string | null;
    state?: string | null;
    date?: string | null;
    amount?: number | null;
    quote?: string | null;
  };
  proposed?: {
    field: string;
    current?: string | null;
    proposed?: string | null;
    quote?: string | null;
    doctor_id?: string | null;
    doctor_name?: string | null;
  } | null;
  safety?: {
    quote?: string | null;
    highlight?: string | null;
    reason?: string | null;
    doctor_id?: string | null;
    doctor_name?: string | null;
  } | null;
  candidates: Array<{
    doctor_id?: string | null;
    name?: string | null;
    npi?: string | null;
    specialty?: string | null;
    city?: string | null;
    state?: string | null;
    practice?: string | null;
    phone?: string | null;
    suffix?: string | null;
    former?: string | null;
    score?: number | null;
    recommended?: boolean;
    no_clear_winner?: boolean;
    grid?: Record<string, [string, string]>;
  }>;
  reasoning?: {
    recommendation: string;
    confidence: string;
    agrees: string[];
    partial: string[];
    conflicts: string[];
    why_not: string[];
    extra: string[];
    margin: number;
    found_by: string;
    score: number;
  } | null;
};

export function fetchReviewWorkspace(signal?: AbortSignal) {
  return apiFetch<ReviewBoard>('/reviews/workspace', { signal });
}

export function resolveBoardItem(body: { item_id: string; action: string; comment: string }) {
  return apiFetch<{ item_id: string; changed_doctor_ids: string[] }>('/reviews/board-decisions', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

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
