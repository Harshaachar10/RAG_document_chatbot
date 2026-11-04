import { SEVERITY_LABELS, RESOLUTION_LABELS, REVIEW_STATUS_LABELS } from '../config/statuses';
import { cn, titleCase } from '../utils/formatters';

const toneMap: Record<string, string> = {
  linked: 'bg-emerald-50 text-emerald-900 border-emerald-200',
  pending: 'bg-amber-50 text-amber-900 border-amber-200',
  deferred: 'bg-slate-100 text-slate-800 border-slate-300',
  completed: 'bg-sky-50 text-sky-900 border-sky-200',
  unresolved: 'bg-orange-50 text-orange-900 border-orange-200',
  review_required: 'bg-amber-50 text-amber-900 border-amber-200',
  identifier_conflict: 'bg-rose-50 text-rose-900 border-rose-200',
  critical: 'bg-rose-50 text-rose-900 border-rose-200',
  high: 'bg-orange-50 text-orange-900 border-orange-200',
  medium: 'bg-amber-50 text-amber-900 border-amber-200',
  low: 'bg-slate-100 text-slate-700 border-slate-300',
  clear: 'bg-emerald-50 text-emerald-900 border-emerald-200',
};

export function StatusBadge({
  value,
  kind = 'generic',
}: {
  value?: string | null;
  kind?: 'resolution' | 'review' | 'severity' | 'generic';
}) {
  if (!value) return <span className="text-sm text-muted">—</span>;
  const label =
    kind === 'resolution'
      ? RESOLUTION_LABELS[value] || titleCase(value)
      : kind === 'review'
        ? REVIEW_STATUS_LABELS[value] || titleCase(value)
        : kind === 'severity'
          ? SEVERITY_LABELS[value] || titleCase(value)
          : titleCase(value);
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
        toneMap[value] || 'bg-slate-50 text-slate-700 border-slate-200',
      )}
      title={label}
    >
      {label}
    </span>
  );
}
