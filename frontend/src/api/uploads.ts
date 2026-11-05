import { apiFetch, getApiBaseUrl } from './client';

export function fetchUploadBatches(signal?: AbortSignal) {
  return apiFetch<{ items: Array<Record<string, unknown>>; total: number }>('/uploads', { signal });
}

export function fetchUploadBatch(batchId: string, signal?: AbortSignal) {
  return apiFetch<Record<string, unknown>>(`/uploads/${batchId}`, { signal });
}

export async function uploadFile(mode: 'structured' | 'document', file: File, uploadedBy = 'Steward') {
  const body = new FormData();
  body.append('mode', mode);
  body.append('file', file);
  body.append('uploaded_by', uploadedBy);
  const res = await fetch(`${getApiBaseUrl()}/uploads`, { method: 'POST', body });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.error?.message || `Upload failed (${res.status})`);
  }
  return res.json() as Promise<Record<string, unknown>>;
}

export function confirmMapping(batchId: string, mapping: Record<string, string>) {
  return apiFetch<Record<string, unknown>>(`/uploads/${batchId}/mapping`, {
    method: 'POST',
    body: JSON.stringify({ mapping }),
  });
}

export function confirmExtract(batchId: string, extracted: Record<string, unknown>) {
  return apiFetch<Record<string, unknown>>(`/uploads/${batchId}/extract`, {
    method: 'POST',
    body: JSON.stringify({ extracted }),
  });
}

export function commitUpload(batchId: string) {
  return apiFetch<Record<string, unknown>>(`/uploads/${batchId}/commit`, { method: 'POST' });
}

export function rollbackUpload(batchId: string) {
  return apiFetch<Record<string, unknown>>(`/uploads/${batchId}/rollback`, { method: 'POST' });
}
