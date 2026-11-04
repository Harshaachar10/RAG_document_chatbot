import { apiFetch, toQuery } from './client';
import type {
  DoctorListItem,
  DoctorSummary,
  HistoryEvent,
  MatchExplanation,
  Paginated,
  SourceRecordItem,
} from './contracts';

export function fetchDoctors(params: Record<string, unknown>, signal?: AbortSignal) {
  return apiFetch<Paginated<DoctorListItem>>(`/doctors${toQuery(params)}`, { signal });
}

export function fetchDoctor(doctorId: string, signal?: AbortSignal) {
  return apiFetch<DoctorSummary>(`/doctors/${doctorId}`, { signal });
}

export function fetchDoctorSourceRecords(doctorId: string, signal?: AbortSignal) {
  return apiFetch<Paginated<SourceRecordItem>>(`/doctors/${doctorId}/source-records`, { signal });
}

export function fetchDoctorHistory(
  doctorId: string,
  params: Record<string, unknown> = {},
  signal?: AbortSignal,
) {
  return apiFetch<Paginated<HistoryEvent>>(`/doctors/${doctorId}/history${toQuery(params)}`, { signal });
}

export function fetchMatchExplanation(doctorId: string, signal?: AbortSignal) {
  return apiFetch<MatchExplanation>(`/doctors/${doctorId}/match-explanation`, { signal });
}

export function fetchDoctorReviewHistory(doctorId: string, signal?: AbortSignal) {
  return apiFetch<Paginated<Record<string, unknown>>>(`/doctors/${doctorId}/review-history`, { signal });
}

export function fetchDoctorAliases(doctorId: string, signal?: AbortSignal) {
  return apiFetch<Array<Record<string, unknown>>>(`/doctors/${doctorId}/aliases`, { signal });
}

export function fetchDoctorAffiliations(doctorId: string, signal?: AbortSignal) {
  return apiFetch<Array<Record<string, unknown>>>(`/doctors/${doctorId}/affiliations`, { signal });
}

export function exportDoctorsUrl() {
  return `${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'}/exports/doctors`;
}
