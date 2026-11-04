import type { ApiErrorBody } from './contracts';

const DEFAULT_BASE = 'http://127.0.0.1:8000/api/v1';

export class ApiError extends Error {
  code: string;
  status: number;
  requestId?: string;
  details?: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody | null, fallback: string) {
    super(body?.error?.message || fallback);
    this.name = 'ApiError';
    this.status = status;
    this.code = body?.error?.code || 'HTTP_ERROR';
    this.requestId = body?.request_id;
    this.details = body?.error?.details;
  }
}

export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL || DEFAULT_BASE;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { signal?: AbortSignal } = {},
): Promise<T> {
  const base = getApiBaseUrl().replace(/\/$/, '');
  const url = path.startsWith('http') ? path : `${base}${path.startsWith('/') ? '' : '/'}${path}`;
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (err) {
    throw new ApiError(0, null, 'Unable to reach the Doctor Intelligence API. Check that the backend is running.');
  }

  if (!response.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = null;
    }
    throw new ApiError(response.status, body, `Request failed (${response.status})`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return (await response.json()) as T;
  }
  return (await response.text()) as T;
}

export function toQuery(params: Record<string, unknown | undefined | null>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    search.set(key, String(value));
  });
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}
