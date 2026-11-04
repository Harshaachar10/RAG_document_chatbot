import { useMemo, useState } from 'react';
import type { HistoryEvent } from '../../../api/contracts';
import { EmptyState } from '../../../components/EmptyState';
import { StatusBadge } from '../../../components/StatusBadge';
import { formatDate } from '../../../utils/dateUtils';
import { displayValue } from '../../../utils/formatters';

const FILTERS = [
  { id: 'all', label: 'All events' },
  { id: 'names', label: 'Names' },
  { id: 'addresses', label: 'Addresses' },
  { id: 'affiliations', label: 'Affiliations' },
  { id: 'record_entries', label: 'Record entries' },
  { id: 'review_decisions', label: 'Review decisions' },
];

export function DoctorTimeline({
  events,
  highlightEventId,
  onOpenEvidence,
  mode = 'timeline',
}: {
  events: HistoryEvent[];
  highlightEventId?: string | null;
  onOpenEvidence: (evidenceId: string) => void;
  mode?: 'timeline' | 'table';
}) {
  const [filter, setFilter] = useState('all');
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const filtered = useMemo(() => {
    const mapping: Record<string, string[]> = {
      names: ['name_variation_observed', 'name_change_documented', 'name_update'],
      addresses: ['address_update', 'address_observed'],
      affiliations: ['affiliation_observed', 'affiliation_effective', 'affiliation_update'],
      record_entries: ['record_entry'],
      review_decisions: ['review_decision', 'preferred_name_approved'],
    };
    let rows = events;
    if (filter !== 'all') {
      const allowed = mapping[filter] || [];
      rows = rows.filter((e) => allowed.includes(e.event_type));
    }
    rows = [...rows].sort((a, b) => {
      const av = a.date_label || '';
      const bv = b.date_label || '';
      return sortDir === 'desc' ? bv.localeCompare(av) : av.localeCompare(bv);
    });
    return rows;
  }, [events, filter, sortDir]);

  const expandAll = () => {
    const next: Record<string, boolean> = {};
    filtered.forEach((e) => {
      next[e.event_id] = true;
    });
    setExpanded(next);
  };

  if (!events.length) {
    return <EmptyState title="No history events" />;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFilter(f.id)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium ${
              filter === f.id ? 'bg-primary text-white' : 'bg-slate-100 text-slate-700'
            }`}
            aria-pressed={filter === f.id}
          >
            {f.label}
          </button>
        ))}
        <button type="button" className="ml-auto text-xs text-primary hover:underline" onClick={() => setSortDir(sortDir === 'desc' ? 'asc' : 'desc')}>
          Sort: {sortDir === 'desc' ? 'Newest' : 'Oldest'}
        </button>
        <button type="button" className="text-xs text-primary hover:underline" onClick={expandAll}>Expand all</button>
        <button type="button" className="text-xs text-primary hover:underline" onClick={() => setExpanded({})}>Collapse all</button>
      </div>

      {mode === 'table' ? (
        <div className="overflow-auto rounded-[12px] border border-border bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-muted">
              <tr>
                <th className="px-3 py-2 text-left">Date</th>
                <th className="px-3 py-2 text-left">Date meaning</th>
                <th className="px-3 py-2 text-left">Event</th>
                <th className="px-3 py-2 text-left">Previous</th>
                <th className="px-3 py-2 text-left">Observed / new</th>
                <th className="px-3 py-2 text-left">Source</th>
                <th className="px-3 py-2 text-left">Decision</th>
                <th className="px-3 py-2 text-left">Evidence</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => (
                <tr key={e.event_id} className={`border-t border-border ${highlightEventId === e.event_id ? 'bg-sky-50' : ''}`}>
                  <td className="px-3 py-2">{formatDate(e.date_label)}</td>
                  <td className="px-3 py-2">{displayValue(e.date_meaning)}</td>
                  <td className="px-3 py-2">{e.title}</td>
                  <td className="px-3 py-2">{displayValue(e.previous_value, '—')}</td>
                  <td className="px-3 py-2">{displayValue(e.new_value, '—')}</td>
                  <td className="px-3 py-2">{displayValue(e.source_type, '—')}</td>
                  <td className="px-3 py-2"><StatusBadge value={e.review_status} kind="review" /></td>
                  <td className="px-3 py-2">
                    {e.evidence_id ? (
                      <button type="button" className="text-primary hover:underline" onClick={() => onOpenEvidence(e.evidence_id!)}>View</button>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <ol className="space-y-3">
          {filtered.map((e) => {
            const open = expanded[e.event_id] || highlightEventId === e.event_id;
            return (
              <li
                key={e.event_id}
                className={`rounded-[12px] border bg-white p-4 shadow-sm ${
                  highlightEventId === e.event_id ? 'border-accent' : 'border-border'
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="text-xs text-muted">{formatDate(e.date_label)} · {displayValue(e.date_meaning)}</div>
                    <h4 className="mt-1 font-semibold">{e.title}</h4>
                    <p className="mt-1 text-sm text-muted">{e.description}</p>
                    {(e.previous_value || e.new_value) ? (
                      <p className="mt-2 text-sm">
                        <span className="text-muted">Change:</span> {displayValue(e.previous_value, '—')} → {displayValue(e.new_value, '—')}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge value={e.review_status} kind="review" />
                    <button
                      type="button"
                      className="text-xs text-primary hover:underline"
                      onClick={() => setExpanded((s) => ({ ...s, [e.event_id]: !open }))}
                    >
                      {open ? 'Collapse' : 'Expand'}
                    </button>
                  </div>
                </div>
                {open ? (
                  <div className="mt-3 grid gap-2 rounded-md bg-slate-50 p-3 text-sm md:grid-cols-2">
                    <div>Document date: {formatDate(e.document_date)}</div>
                    <div>Submitted at: {displayValue(e.submitted_at, 'Not recorded')}</div>
                    <div>Submitted to: {displayValue(e.submitted_to, 'Not recorded')}</div>
                    <div>Effective from: {e.effective_date ? formatDate(e.effective_date) : 'Unknown'}</div>
                    <div>Recorded at: {displayValue(e.recorded_at)}</div>
                    <div>Source type: {displayValue(e.source_type)}</div>
                    <div className="md:col-span-2">Quotation: {displayValue(e.evidence_quotation, 'None')}</div>
                    {e.evidence_id ? (
                      <button type="button" className="text-left text-sm font-medium text-primary hover:underline" onClick={() => onOpenEvidence(e.evidence_id!)}>
                        View evidence
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ol>
      )}
      {!filtered.length ? <EmptyState title="No events for this filter" /> : null}
    </div>
  );
}

export function FieldHistoryTable(props: {
  events: HistoryEvent[];
  highlightEventId?: string | null;
  onOpenEvidence: (evidenceId: string) => void;
}) {
  return <DoctorTimeline {...props} mode="table" />;
}
