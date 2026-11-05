import { apiFetch, toQuery } from './client';

export function fetchNotesInsights(params: Record<string, unknown> = {}, signal?: AbortSignal) {
  return apiFetch<{ items: Array<Record<string, unknown>>; total: number }>(
    `/notes/insights${toQuery(params)}`,
    { signal },
  );
}
