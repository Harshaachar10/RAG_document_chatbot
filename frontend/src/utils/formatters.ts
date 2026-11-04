export function displayValue(value: unknown, fallback = 'Not available'): string {
  if (value === null || value === undefined || value === '') return fallback;
  return String(value);
}

export function titleCase(value: string): string {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}

export function percent(value?: number | null): string {
  if (value === null || value === undefined) return '—';
  return `${Math.round(value * 100)}%`;
}
