import type { SourceRecordItem } from '../../../api/contracts';
import { Dialog } from '../../../components/Dialog';
import { StatusBadge } from '../../../components/StatusBadge';
import { formatDate } from '../../../utils/dateUtils';
import { displayValue } from '../../../utils/formatters';

function missingFields(record: SourceRecordItem) {
  const gaps: string[] = [];
  const identifier = record.provider_identifier || (record.normalized?.provider_identifier as string | undefined);
  const kind = String(record.identifier_kind || record.normalized?.identifier_kind || '').toLowerCase();
  if (!identifier || ['missing', 'absent', 'none'].includes(String(identifier).toLowerCase()) || kind === 'missing') {
    gaps.push('NPI / provider identifier');
  }
  if (!record.address_line && !record.city) gaps.push('Address');
  if (!record.practice_name) gaps.push('Practice / affiliation');
  if (!record.email && !record.phone) gaps.push('Contact details');
  return gaps;
}

export function SourceRecordDetail({
  record,
  open,
  onOpenChange,
  onOpenEvidence,
}: {
  record: SourceRecordItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onOpenEvidence?: (evidenceId: string) => void;
}) {
  if (!record) return null;
  const gaps = missingFields(record);
  const provided = [
    ['Name', record.recorded_name],
    ['Specialty', record.specialty],
    ['Practice', record.practice_name],
    ['Address', record.address_line],
    ['City / state', [record.city, record.state].filter(Boolean).join(', ')],
    ['Email', record.email],
    ['Phone', record.phone],
    ['Credential', record.credential_reference],
  ].filter(([, value]) => Boolean(value));

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={record.source_record_id}
      description={`${displayValue(record.source_name || record.source_id)} · ${displayValue(record.record_kind)}`}
      size="spacious"
      footer={(
        <button
          type="button"
          className="rounded-md border border-border px-3 py-2 text-sm"
          onClick={() => onOpenChange(false)}
        >
          Close
        </button>
      )}
    >
      <div className="space-y-4 text-sm">
        <div className="flex flex-wrap gap-2">
          <StatusBadge value={record.link_status || record.resolution_status} kind="resolution" />
          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs">Document date: {formatDate(record.record_date)}</span>
          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs">Submitted: {formatDate(record.submitted_at)}</span>
        </div>

        <section className="grid gap-3 md:grid-cols-2">
          <div className="rounded-[12px] border border-emerald-200 bg-emerald-50 p-3">
            <h4 className="font-semibold text-emerald-950">Provided on this record</h4>
            <ul className="mt-2 space-y-1">
              {provided.length ? provided.map(([label, value]) => (
                <li key={String(label)}><span className="text-muted">{label}:</span> {displayValue(value)}</li>
              )) : <li>No core identity fields recorded</li>}
            </ul>
          </div>
          <div className="rounded-[12px] border border-amber-200 bg-amber-50 p-3">
            <h4 className="font-semibold text-amber-950">Missing on this record</h4>
            <ul className="mt-2 space-y-1">
              {gaps.length ? gaps.map((gap) => <li key={gap}>{gap}</li>) : <li>No critical gaps highlighted</li>}
            </ul>
          </div>
        </section>

        <section className="rounded-[12px] border border-border bg-white p-3">
          <h4 className="font-semibold">Submission context</h4>
          <dl className="mt-2 grid gap-2 md:grid-cols-2">
            <div><dt className="text-muted">Submitted by</dt><dd>{displayValue(record.submitted_by, 'Not recorded')}</dd></div>
            <div><dt className="text-muted">Submitted to</dt><dd>{displayValue(record.submitted_to, 'Not recorded')}</dd></div>
            <div className="md:col-span-2"><dt className="text-muted">Linkage note</dt><dd>{displayValue(record.linkage_explanation, '—')}</dd></div>
          </dl>
        </section>

        <section className="rounded-[12px] border border-border bg-white p-3">
          <h4 className="font-semibold">Evidence</h4>
          <div className="mt-2 flex flex-wrap gap-2">
            {record.evidence_ids.length ? record.evidence_ids.map((id) => (
              <button
                key={id}
                type="button"
                className="rounded-md border border-border px-2.5 py-1 text-primary hover:bg-slate-50"
                onClick={() => {
                  onOpenEvidence?.(id);
                  onOpenChange(false);
                }}
              >
                Open {id}
              </button>
            )) : <span className="text-muted">No evidence linked</span>}
          </div>
        </section>
      </div>
    </Dialog>
  );
}
