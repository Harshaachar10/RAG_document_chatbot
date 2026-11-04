import { apiFetch, toQuery } from './client';
import type { DemoRun, Paginated, QualitySummary, SourceSummary } from './contracts';

export function fetchSources(signal?: AbortSignal) {
  return apiFetch<Paginated<SourceSummary>>('/sources', { signal });
}

export function fetchSourceRecords(sourceId: string, params: Record<string, unknown> = {}, signal?: AbortSignal) {
  return apiFetch<Paginated<Record<string, unknown>>>(`/sources/${sourceId}/records${toQuery(params)}`, { signal });
}

export function fetchSourceRecord(recordId: string, signal?: AbortSignal) {
  return apiFetch<Record<string, unknown>>(`/source-records/${recordId}`, { signal });
}

export function fetchDemoRuns(signal?: AbortSignal) {
  return apiFetch<Paginated<DemoRun>>('/demo-runs', { signal });
}

export function startDemoRun() {
  return apiFetch<DemoRun>('/demo-runs', { method: 'POST' });
}

export function fetchDemoRun(runId: string, signal?: AbortSignal) {
  return apiFetch<DemoRun>(`/demo-runs/${runId}`, { signal });
}

export function fetchQualitySummary(signal?: AbortSignal) {
  return apiFetch<QualitySummary>('/quality/summary', { signal });
}

export function fetchActivity(params: Record<string, unknown> = {}, signal?: AbortSignal) {
  return apiFetch<Paginated<Record<string, unknown>>>(`/activity${toQuery(params)}`, { signal });
}
