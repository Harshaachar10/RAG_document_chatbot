import { Fragment, useState } from 'react';
import { EmptyState } from '../../../components/EmptyState';
import { StatusBadge } from '../../../components/StatusBadge';
import { formatDate } from '../../../utils/dateUtils';
import { displayValue } from '../../../utils/formatters';

export function SourceRecordsTable({
  rows,
  selectedIds,
  onToggle,
}: {
  rows: Array<Record<string, unknown>>;
  selectedIds?: Set<string>;
  onToggle?: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  if (!rows.length) {
    return <EmptyState title="No source records" description="No rows match the current filters." />;
  }
  return (
    <div className="overflow-auto rounded-[12px] border border-border bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-muted">
          <tr>
            <th className="px-3 py-2 text-left">Select</th>
            <th className="px-3 py-2 text-left">Record ID</th>
            <th className="px-3 py-2 text-left">Type</th>
            <th className="px-3 py-2 text-left">Name</th>
            <th className="px-3 py-2 text-left">Practice</th>
            <th className="px-3 py-2 text-left">Date</th>
            <th className="px-3 py-2 text-left">Status</th>
            <th className="px-3 py-2 text-left">Master</th>
            <th className="px-3 py-2 text-left">Inspect</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const id = String(row.source_record_id);
            return (
              <Fragment key={id}>
                <tr className="border-t border-border">
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      aria-label={`Select ${id}`}
                      checked={!!selectedIds?.has(id)}
                      onChange={() => onToggle?.(id)}
                    />
                  </td>
                  <td className="px-3 py-2">{id}</td>
                  <td className="px-3 py-2">{displayValue(row.record_kind)}</td>
                  <td className="px-3 py-2">{displayValue(row.recorded_name)}</td>
                  <td className="px-3 py-2">{displayValue(row.practice_name)}</td>
                  <td className="px-3 py-2">{formatDate(String(row.record_date || ''))}</td>
                  <td className="px-3 py-2">
                    <StatusBadge value={String(row.resolution_status || '')} kind="resolution" />
                  </td>
                  <td className="px-3 py-2">{displayValue(row.doctor_id, '—')}</td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      className="text-primary hover:underline"
                      onClick={() => setExpanded(expanded === id ? null : id)}
                    >
                      {expanded === id ? 'Hide' : 'Inspect'}
                    </button>
                  </td>
                </tr>
                {expanded === id ? (
                  <tr className="border-t border-border bg-slate-50">
                    <td colSpan={9} className="px-4 py-3 text-sm">
                      <div className="grid gap-2 md:grid-cols-2">
                        <div>Email: {displayValue(row.email)}</div>
                        <div>Credential: {displayValue(row.credential_reference)}</div>
                        <div>City/State: {[row.city, row.state].filter(Boolean).join(', ') || '—'}</div>
                        <div>Document: {displayValue(row.document_id, 'None')}</div>
                      </div>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
