import { apiFetch, getApiBaseUrl } from './client';
import type { DocumentDetail, EvidenceDetail } from './contracts';

export function fetchEvidence(evidenceId: string, signal?: AbortSignal) {
  return apiFetch<EvidenceDetail>(`/evidence/${evidenceId}`, { signal });
}

export function fetchDocument(documentId: string, signal?: AbortSignal, version?: string | number | null) {
  const query = version === undefined || version === null || version === '' ? '' : `?version=${encodeURIComponent(String(version))}`;
  return apiFetch<DocumentDetail>(`/documents/${documentId}${query}`, { signal });
}

export function documentDownloadUrl(documentId: string) {
  return `${getApiBaseUrl()}/documents/${documentId}/download`;
}
