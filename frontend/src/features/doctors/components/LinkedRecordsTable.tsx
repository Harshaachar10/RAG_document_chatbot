import { useMemo, useState } from 'react';
import type { SourceRecordItem } from '../../../api/contracts';
import { EmptyState } from '../../../components/EmptyState';
import { StatusBadge } from '../../../components/StatusBadge';
import { formatDate } from '../../../utils/dateUtils';
import { displayValue } from '../../../utils/formatters';

export function LinkedRecordsTable({
  records,
  onOpenEvidence,
  onOpenRecord,
  aliasFilter,
}: {
  records: SourceRecordItem[];
  onOpenEvidence: (evidenceId: string) => void;
  onOpenRecord?: (record: SourceRecordItem) => void;
  aliasFilter?: string | null;
}) {
  const [sourceFilter, setSourceFilter] = useState('');
  const [kindFilter, setKindFilter] = useState('');

  const filtered = useMemo(() => {
    return records.filter((r) => {
      if (sourceFilter && r.source_id !== sourceFilter) return false;
      if (kindFilter && r.record_kind !== kindFilter) return false;
      if (aliasFilter && !(r.recorded_name || '').toLowerCase().includes(aliasFilter.toLowerCase())) return false;
      return true;
    });
  }, [records, sourceFilter, kindFilter, aliasFilter]);

  const sources = Array.from(new Set(records.map((r) => r.source_id)));

  function openRow(row: SourceRecordItem) {
    if (onOpenRecord) {
      onOpenRecord(row);
      return;
    }
    if (row.evidence_ids[0]) onOpenEvidence(row.evidence_ids[0]);
  }

  if (!records.length) {
    return <EmptyState title="No linked records" description="No source records are linked to this doctor." />;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <select
          className="rounded-md border border-border px-2 py-1.5 text-sm"
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          aria-label="Filter by source"
        >
          <option value="">All sources</option>
          {sources.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          className="rounded-md border border-border px-2 py-1.5 text-sm"
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value)}
          aria-label="Filter by type"
        >
          <option value="">All types</option>
          <option value="identity_entry">Identity entry</option>
          <option value="supporting_transaction">Supporting transaction</option>
          <option value="note_observation">Note observation</option>
        </select>
      </div>
      <div className="overflow-auto rounded-[12px] border border-border bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-muted">
            <tr>
              <th className="px-3 py-2 text-left">Record ID</th>
              <th className="px-3 py-2 text-left">Source / type</th>
              <th className="px-3 py-2 text-left">Name recorded</th>
              <th className="px-3 py-2 text-left">Affiliation / address</th>
              <th className="px-3 py-2 text-left">Document date</th>
              <th className="px-3 py-2 text-left">Link status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr
                key={row.source_record_id}
                className="cursor-pointer border-t border-border hover:bg-slate-50"
                onClick={() => openRow(row)}
              >
                <td className="px-3 py-2 font-medium text-primary">{row.source_record_id}</td>
                <td className="px-3 py-2">
                  {row.source_name || row.source_id}
                  <div className="text-xs text-muted">{row.record_kind}</div>
                </td>
                <td className="px-3 py-2">{displayValue(row.recorded_name)}</td>
                <td className="px-3 py-2">
                  {displayValue(row.practice_name)}
                  <div className="text-xs text-muted">{[row.city, row.state].filter(Boolean).join(', ') || '—'}</div>
                </td>
                <td className="px-3 py-2">{formatDate(row.record_date)}</td>
                <td className="px-3 py-2">
                  <StatusBadge value={row.link_status || row.resolution_status} kind="resolution" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!filtered.length ? <EmptyState title="No records match filters" /> : null}
    </div>
  );
}
