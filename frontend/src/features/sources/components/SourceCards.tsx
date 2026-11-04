import type { SourceSummary } from '../../../api/contracts';
import { formatDate } from '../../../utils/dateUtils';
import { percent } from '../../../utils/formatters';

export function SourceCards({
  sources,
  selectedId,
  onSelect,
}: {
  sources: SourceSummary[];
  selectedId?: string;
  onSelect: (sourceId: string) => void;
}) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {sources.map((s) => (
        <button
          key={s.source_id}
          type="button"
          onClick={() => onSelect(s.source_id)}
          className={`rounded-[12px] border p-4 text-left shadow-sm transition ${
            selectedId === s.source_id ? 'border-primary bg-sky-50' : 'border-border bg-white hover:border-accent'
          }`}
          aria-pressed={selectedId === s.source_id}
        >
          <div className="font-semibold">{s.source_name}</div>
          <div className="mt-1 text-xs text-muted">{s.source_type}</div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
            <div>Rows: {s.row_count}</div>
            <div>Linked: {s.linked_count}</div>
            <div>Pending: {s.pending_count}</div>
            <div>Unresolved: {s.unresolved_count}</div>
          </div>
          <div className="mt-2 text-xs text-muted">
            Latest: {formatDate(s.latest_data_date)} · Completeness: {percent(s.completeness)}
          </div>
        </button>
      ))}
    </div>
  );
}
