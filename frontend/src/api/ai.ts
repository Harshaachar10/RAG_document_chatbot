import { apiFetch, toQuery } from './client';
import type { AiAnalysis, AiJob } from './contracts';

export function startIdentityAnalysis(sourceRecordIds: string[], forceRefresh = false) {
  return apiFetch<AiJob>('/ai/identity-analyses', {
    method: 'POST',
    body: JSON.stringify({ source_record_ids: sourceRecordIds, force_refresh: forceRefresh }),
  });
}

export function startChangeExtraction(sourceRecordIds: string[], forceRefresh = false) {
  return apiFetch<AiJob>('/ai/change-extractions', {
    method: 'POST',
    body: JSON.stringify({ source_record_ids: sourceRecordIds, force_refresh: forceRefresh }),
  });
}

export function startProfileSummary(doctorId: string, forceRefresh = false) {
  return apiFetch<AiJob>(`/doctors/${doctorId}/ai-summary`, {
    method: 'POST',
    body: JSON.stringify({ force_refresh: forceRefresh }),
  });
}

export function fetchProfileSummary(doctorId: string, signal?: AbortSignal) {
  return apiFetch<{ available: boolean; analysis?: AiAnalysis | null }>(`/doctors/${doctorId}/ai-summary`, { signal });
}

export function startReviewExplanation(reviewId: string, forceRefresh = false) {
  return apiFetch<AiJob>(`/reviews/${reviewId}/ai-explanation`, {
    method: 'POST',
    body: JSON.stringify({ force_refresh: forceRefresh }),
  });
}

export function fetchAiJob(jobId: string, signal?: AbortSignal) {
  return apiFetch<AiJob>(`/ai/jobs/${jobId}`, { signal });
}

export function fetchAiJobs(signal?: AbortSignal) {
  return apiFetch<{ items: AiJob[]; total: number }>('/ai/jobs?limit=20', { signal });
}

export function fetchAiAnalyses(params: Record<string, unknown> = {}, signal?: AbortSignal) {
  return apiFetch<{ items: AiAnalysis[]; total: number }>(`/ai/analyses${toQuery(params)}`, { signal });
}
