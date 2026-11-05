import { displayValue } from '../../../utils/formatters';
import { PIPELINE_ACTION_LABELS } from '../../../config/statuses';

type Contribution = {
  field?: string;
  status?: string;
  detail?: string;
  delta?: number;
};

type Candidate = {
  candidate_doctor_id?: string;
  doctor_name?: string | null;
  demo_score?: number | null;
  evidence_summary?: string | null;
  target_id?: string;
  target_source?: string;
  hard_stops?: Array<{ code?: string; message?: string }>;
  contributions?: Contribution[];
  rank?: number;
};

export function PipelineMatchPanel({
  pipelineAction,
  pipelineReason,
  pipelineScore,
  queue,
  recordFlags,
  candidates,
}: {
  pipelineAction?: string | null;
  pipelineReason?: string | null;
  pipelineScore?: number | null;
  queue?: string | null;
  recordFlags?: Array<{ code?: string; message?: string }>;
  candidates?: Candidate[];
}) {
  if (!pipelineAction && !(candidates || []).length) return null;

  return (
    <div className="space-y-4">
      <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold">Pipeline routing</h3>
        <dl className="mt-3 grid gap-2 text-sm md:grid-cols-4">
          <div>
            <dt className="text-muted">Action</dt>
            <dd className="font-medium">
              {PIPELINE_ACTION_LABELS[pipelineAction || ''] || displayValue(pipelineAction)}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Score</dt>
            <dd className="font-medium">
              {pipelineScore == null ? '—' : Number(pipelineScore).toFixed(3)}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Queue</dt>
            <dd className="font-medium">{displayValue(queue, '—')}</dd>
          </div>
          <div>
            <dt className="text-muted">Reason</dt>
            <dd className="font-medium">{displayValue(pipelineReason, '—')}</dd>
          </div>
        </dl>
        {(recordFlags || []).length ? (
          <ul className="mt-3 space-y-1 text-sm">
            {recordFlags!.map((f, i) => (
              <li key={i} className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-amber-950">
                <span className="font-medium">{f.code}</span>: {f.message}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      {(candidates || []).length ? (
        <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold">Scored candidates</h3>
          <div className="mt-3 space-y-3">
            {candidates!.map((c, idx) => (
              <div key={idx} className="rounded-md border border-border p-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <div className="font-medium">
                      #{c.rank || idx + 1} {displayValue(c.doctor_name || c.target_id)}
                    </div>
                    <div className="text-xs text-muted">
                      {displayValue(c.target_source)} · {displayValue(c.target_id || c.candidate_doctor_id)}
                    </div>
                  </div>
                  <div className="text-sm font-semibold">
                    {c.demo_score == null ? '—' : Number(c.demo_score).toFixed(3)}
                  </div>
                </div>
                {c.evidence_summary ? <p className="mt-2 text-sm text-muted">{c.evidence_summary}</p> : null}
                {(c.hard_stops || []).length ? (
                  <ul className="mt-2 space-y-1 text-sm text-rose-800">
                    {c.hard_stops!.map((h, i) => (
                      <li key={i}>Hard stop {h.code}: {h.message}</li>
                    ))}
                  </ul>
                ) : null}
                {(c.contributions || []).length ? (
                  <div className="mt-2 overflow-auto">
                    <table className="min-w-full text-xs">
                      <thead className="text-muted">
                        <tr>
                          <th className="px-2 py-1 text-left">Field</th>
                          <th className="px-2 py-1 text-left">Status</th>
                          <th className="px-2 py-1 text-left">Detail</th>
                          <th className="px-2 py-1 text-right">Δ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {c.contributions!.map((row, i) => (
                          <tr key={i} className="border-t border-border">
                            <td className="px-2 py-1">{row.field}</td>
                            <td className="px-2 py-1">{row.status}</td>
                            <td className="px-2 py-1">{row.detail}</td>
                            <td className="px-2 py-1 text-right">{row.delta ?? ''}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
