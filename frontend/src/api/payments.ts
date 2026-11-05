import { apiFetch, toQuery } from './client';

export function fetchPaymentCompliance(params: Record<string, unknown> = {}, signal?: AbortSignal) {
  return apiFetch<{ items: Array<Record<string, unknown>>; total: number; policy?: string }>(
    `/payments/compliance${toQuery(params)}`,
    { signal },
  );
}
