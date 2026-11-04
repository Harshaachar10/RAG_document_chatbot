import { useMemo, useState } from 'react';
import type { HistoryEvent } from '../../../api/contracts';
import { EmptyState } from '../../../components/EmptyState';
import { StatusBadge } from '../../../components/StatusBadge';
import { formatDate } from '../../../utils/dateUtils';
import { displayValue } from '../../../utils/formatters';

const FILTERS = [
  { id: 'all', label: 'All events' },
  { id: 'issues', label: 'Issues & gaps' },
  { id: 'names', label: 'Names' },
  { id: 'addresses', label: 'Addresses' },
  { id: 'affiliations', label: 'Affiliations' },
  { id: 'identifiers', label: 'Identifiers / NPI' },
  { id: 'duplicates', label: 'Duplicates' },
  { id: 'record_entries', label: 'Record entries' },
  { id: 'review_decisions', label: 'Review decisions' },
];

const FILTER_TYPES: Record<string, string[]> = {
  names: ['name_variation_observed', 'name_change_documented', 'name_update'],
  addresses: ['address_update', 'address_observed', 'contact_update'],
  affiliations: ['affiliation_observed', 'affiliation_effective', 'affiliation_update'],
  identifiers: ['identifier_conflict', 'identifier_missing', 'npi_missing'],
  duplicates: ['possible_duplicate', 'duplicate_ingestion'],
  issues: [
    'identifier_conflict',
    'identifier_missing',
    'npi_missing',
    'possible_duplicate',
    'duplicate_ingestion',
    'name_update',
    'affiliation_update',
    'contact_update',
    'address_update',
  ],
  record_entries: ['record_entry'],
  review_decisions: ['review_decision', 'preferred_name_approved'],
};

function isIssue(event: HistoryEvent) {
  if (event.gaps?.length) return true;
  if (event.issue_category && !['activity', 'review'].includes(event.issue_category)) return true;
  return FILTER_TYPES.issues.includes(event.event_type);
}

function matchesFilter(event: HistoryEvent, filter: string) {
  if (filter === 'all') return true;
  const allowed = FILTER_TYPES[filter] || [];
  if (allowed.includes(event.event_type)) return true;
  if (filter === 'issues') return isIssue(event);
  if (filter === 'addresses') {
    return event.issue_category === 'address_change' || /address/i.test(`${event.title} ${event.description || ''}`);
  }
  if (filter === 'identifiers') {
    return (
      event.issue_category === 'identifier_issue' ||
      event.issue_category === 'missing_field' ||
      (event.gaps || []).some((g) => /npi|identifier/i.test(g))
    );
  }
  return false;
}

export function DoctorTimeline({
  events,
  highlightEventId,
  onOpenEvidence,
  mode = 'timeline',
  trailSummary,
}: {
  events: HistoryEvent[];
  highlightEventId?: string | null;
  onOpenEvidence: (evidenceId: string) => void;
  mode?: 'timeline' | 'table';
  trailSummary?: { total_events?: number; issue_events?: number; message?: string } | null;
}) {
  const [filter, setFilter] = useState('all');
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const filtered = useMemo(() => {
    let rows = events.filter((e) => matchesFilter(e, filter));
    rows = [...rows].sort((a, b) => {
      const av = a.date_label || a.document_date || '';
      const bv = b.date_label || b.document_date || '';
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
    return <EmptyState title="No history events" description="No chronological identity activity is linked to this person yet." />;
  }

  return (
    <div className="space-y-3">
      {trailSummary?.message ? (
        <div className="rounded-[12px] border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950">
          <p className="font-medium">Identity trail</p>
          <p className="mt-1">{trailSummary.message}</p>
          <p className="mt-1 text-xs text-sky-800">
            Each row is evidence of work or data this person left behind — address changes, meetings, missing NPI, and other gaps — so you can backtrack that it maps to one identity.
          </p>
        </div>
      ) : null}

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
                <th className="px-3 py-2 text-left">Issue</th>
                <th className="px-3 py-2 text-left">Event</th>
                <th className="px-3 py-2 text-left">Gaps</th>
                <th className="px-3 py-2 text-left">Previous</th>
                <th className="px-3 py-2 text-left">Observed / new</th>
                <th className="px-3 py-2 text-left">Source</th>
                <th className="px-3 py-2 text-left">Evidence</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => (
                <tr key={e.event_id} className={`border-t border-border ${highlightEventId === e.event_id ? 'bg-sky-50' : ''}`}>
                  <td className="px-3 py-2">{formatDate(e.date_label || e.document_date)}</td>
                  <td className="px-3 py-2">{displayValue(e.issue_label, '—')}</td>
                  <td className="px-3 py-2">{e.title}</td>
                  <td className="px-3 py-2">{e.gaps?.length ? e.gaps.join('; ') : '—'}</td>
                  <td className="px-3 py-2">{displayValue(e.previous_value, '—')}</td>
                  <td className="px-3 py-2">{displayValue(e.new_value, '—')}</td>
                  <td className="px-3 py-2">{displayValue(e.source_type, '—')}</td>
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
            const issue = isIssue(e);
            const open = expanded[e.event_id] || highlightEventId === e.event_id || issue;
            return (
              <li
                key={e.event_id}
                className={`rounded-[12px] border bg-white p-4 shadow-sm ${
                  highlightEventId === e.event_id ? 'border-accent' : issue ? 'border-amber-300' : 'border-border'
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="text-xs text-muted">
                      {formatDate(e.date_label || e.document_date)} · {displayValue(e.date_meaning)}
                      {e.activity_label ? ` · ${e.activity_label}` : ''}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <h4 className="font-semibold">{e.title}</h4>
                      {e.issue_label ? (
                        <span className={`rounded-md px-2 py-0.5 text-[11px] font-medium ${issue ? 'bg-amber-100 text-amber-950' : 'bg-slate-100 text-slate-700'}`}>
                          {e.issue_label}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-sm text-muted">{e.description}</p>
                    {e.gaps?.length ? (
                      <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm text-amber-950">
                        {e.gaps.map((gap) => (
                          <li key={gap}>{gap}</li>
                        ))}
                      </ul>
                    ) : null}
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
                    <div>Source record: {displayValue(e.source_record_id, '—')}</div>
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
  trailSummary?: { total_events?: number; issue_events?: number; message?: string } | null;
}) {
  return <DoctorTimeline {...props} mode="table" />;
}
