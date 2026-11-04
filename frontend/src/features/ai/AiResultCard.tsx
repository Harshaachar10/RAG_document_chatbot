import type { AiAnalysis, AiJob } from '../../api/contracts';
import { formatDateTime } from '../../utils/dateUtils';
import { displayValue } from '../../utils/formatters';

const STATUS_LABELS: Record<string, string> = {
  queued: 'Queued',
  preparing_evidence: 'Preparing evidence',
  calling_model: 'Calling model',
  validating_response: 'Validating response',
  completed: 'Completed',
  failed: 'Failed',
  interrupted: 'Interrupted',
};

export function AiResultCard({
  job,
  error,
  onOpenEvidence,
  onRefresh,
  refreshDisabled,
}: {
  job?: AiJob | null;
  error?: string | null;
  onOpenEvidence?: (evidenceId: string) => void;
  onRefresh?: () => void;
  refreshDisabled?: boolean;
}) {
  if (error) {
    return <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900">{error}</div>;
  }
  if (!job) return null;
  const analysis = job.analysis;
  const response = (analysis?.response || {}) as Record<string, unknown>;
  const previously = job.cached || analysis?.cached || analysis?.served_from_cache;
  return (
    <section className="space-y-3 rounded-[12px] border border-border bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-muted">
            {STATUS_LABELS[job.status] || job.status}
          </div>
          {analysis?.label ? <h3 className="mt-1 text-sm font-semibold">{analysis.label}</h3> : null}
          {previously && analysis?.completed_at ? (
            <p className="text-xs text-muted">Previously generated {formatDateTime(analysis.completed_at)}</p>
          ) : null}
          {analysis?.completed_at && !previously ? (
            <p className="text-xs text-muted">Generated {formatDateTime(analysis.completed_at)}</p>
          ) : null}
        </div>
        {onRefresh ? (
          <button
            type="button"
            className="rounded-md border border-border px-3 py-1.5 text-sm disabled:opacity-50"
            onClick={onRefresh}
            disabled={refreshDisabled}
          >
            Refresh AI analysis
          </button>
        ) : null}
      </div>

      {job.status !== 'completed' && job.status !== 'failed' && job.status !== 'interrupted' ? (
        <p className="text-sm text-muted">Working: {STATUS_LABELS[job.status] || job.status}. This does not estimate a percent complete.</p>
      ) : null}
      {job.error?.message ? <p className="text-sm text-rose-800">{job.error.message}</p> : null}

      {analysis?.outcome === 'narrowing_required' ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm">
          <p>{displayValue(response.reason)}</p>
          <ul className="mt-2 list-disc pl-5">
            {((response.groups as Array<Record<string, unknown>>) || []).map((group) => (
              <li key={String(group.group_id)}>
                Group {displayValue(group.group_id)} · {displayValue(group.size)} records
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {response.recommendation ? (
        <p className="text-sm"><span className="font-medium">Recommendation:</span> {displayValue(response.recommendation)}</p>
      ) : null}
      {response.summary ? <p className="text-sm">{String(response.summary)}</p> : null}
      {response.why_review ? <p className="text-sm">{String(response.why_review)}</p> : null}
      {response.current_profile ? <p className="text-sm">{String(response.current_profile)}</p> : null}
      {response.affiliation_summary ? <p className="text-sm">{String(response.affiliation_summary)}</p> : null}

      <StringList title="Missing information" values={response.missing_information} />
      <StringList title="Contradictions" values={response.contradictions || response.conflicting_observations || response.conflicts} />
      <StringList title="Outstanding proposals" values={response.outstanding_proposals} />
      <StringList title="Previous names" values={response.previous_names} />

      {Array.isArray(response.proposed_changes) && response.proposed_changes.length ? (
        <div>
          <h4 className="text-sm font-semibold">Proposed changes</h4>
          <ul className="mt-2 space-y-2 text-sm">
            {response.proposed_changes.map((change, index) => {
              const row = change as Record<string, unknown>;
              return (
                <li key={index} className="rounded-md border border-border px-3 py-2">
                  {displayValue(row.field)} → {displayValue(row.proposed_value)}
                  <div className="text-xs text-muted">
                    {displayValue(row.change_type)} · effective {displayValue(row.effective_date, 'unknown')}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      <EvidenceLinks
        title="Supporting evidence"
        ids={(response.supporting_evidence_ids as string[]) || []}
        display={analysis?.evidence_display}
        onOpen={onOpenEvidence}
      />
      <EvidenceLinks
        title="Contradictory evidence"
        ids={(response.conflicting_evidence_ids as string[]) || []}
        display={analysis?.evidence_display}
        onOpen={onOpenEvidence}
      />
    </section>
  );
}

function StringList({ title, values }: { title: string; values: unknown }) {
  const items = Array.isArray(values) ? values.map(String).filter(Boolean) : [];
  if (!items.length) return null;
  return (
    <div>
      <h4 className="text-sm font-semibold">{title}</h4>
      <ul className="mt-1 list-disc pl-5 text-sm">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

function EvidenceLinks({
  title,
  ids,
  display,
  onOpen,
}: {
  title: string;
  ids: string[];
  display?: Array<Record<string, unknown>>;
  onOpen?: (evidenceId: string) => void;
}) {
  if (!ids.length) return null;
  const labels = new Map((display || []).map((row) => [String(row.evidence_id), String(row.citation_label || row.evidence_id)]));
  return (
    <div>
      <h4 className="text-sm font-semibold">{title}</h4>
      <ul className="mt-1 space-y-1 text-sm">
        {ids.map((id) => (
          <li key={id}>
            <button type="button" className="text-primary hover:underline" onClick={() => onOpen?.(id)}>
              {labels.get(id) || id}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
