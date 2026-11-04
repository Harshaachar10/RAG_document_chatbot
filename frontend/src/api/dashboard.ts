import { apiFetch, toQuery } from './client';
import type { DashboardSummary, ReferenceData, SourceBreakdownResponse, HealthResponse } from './contracts';

export function fetchHealth(signal?: AbortSignal) {
  return apiFetch<HealthResponse>('/health', { signal });
}

export function fetchReferenceData(signal?: AbortSignal) {
  return apiFetch<ReferenceData>('/reference-data', { signal });
}

export function fetchDashboardSummary(params: Record<string, unknown> = {}, signal?: AbortSignal) {
  return apiFetch<DashboardSummary>(`/dashboard/summary${toQuery(params)}`, { signal });
}

export function fetchSourceBreakdown(params: Record<string, unknown> = {}, signal?: AbortSignal) {
  return apiFetch<SourceBreakdownResponse>(`/dashboard/source-breakdown${toQuery(params)}`, { signal });
}
