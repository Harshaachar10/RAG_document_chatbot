import type { MatchExplanation as Match } from '../../../api/contracts';
import { displayValue } from '../../../utils/formatters';

export function MatchExplanation({
  data,
  onOpenEvidence,
  onOpenSourceRecord,
}: {
  data: Match;
  onOpenEvidence?: (evidenceId: string) => void;
  onOpenSourceRecord?: (sourceRecordId: string) => void;
}) {
  return (
    <div className="space-y-4">
      <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold">Why these records may belong together</h3>
        <p className="mt-2 text-sm">{data.summary}</p>
        <dl className="mt-3 grid gap-2 text-sm md:grid-cols-3">
          <div><dt className="text-muted">Decision method</dt><dd className="font-medium">{displayValue(data.decision_method)}</dd></div>
          <div><dt className="text-muted">Review status</dt><dd className="font-medium">{displayValue(data.review_status, 'n/a')}</dd></div>
          <div><dt className="text-muted">Linked rows shown</dt><dd className="font-medium">{data.side_by_side.length}</dd></div>
        </dl>
      </section>

      {data.side_by_side.length ? (
        <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold">Supporting records</h3>
          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {data.side_by_side.map((row, idx) => {
              const sourceRecordId = String(row.source_record_id || '');
              return (
                <button
                  key={idx}
                  type="button"
                  className="rounded-md border border-border p-3 text-left text-sm hover:border-primary hover:bg-slate-50"
                  onClick={() => sourceRecordId && onOpenSourceRecord?.(sourceRecordId)}
                >
                  {Object.entries(row).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-2 border-b border-border py-1 last:border-0">
                      <span className="text-muted">{k}</span>
                      <span>{displayValue(v)}</span>
                    </div>
                  ))}
                </button>
              );
            })}
          </div>
        </section>
      ) : null}

      <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold">Evidence assessment</h3>
        <div className="mt-3 overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-muted">
              <tr>
                <th className="px-3 py-2 text-left">Observation</th>
                <th className="px-3 py-2 text-left">Supports / conflicts</th>
                <th className="px-3 py-2 text-left">Explanation</th>
                <th className="px-3 py-2 text-left">Citation</th>
              </tr>
            </thead>
            <tbody>
              {(data.evidence_rows || []).map((row, idx) => {
                const citation = String(row.citation || '');
                const evidenceId = String(row.evidence_id || '');
                return (
                  <tr key={idx} className="border-t border-border">
                    <td className="px-3 py-2">{displayValue(row.observation)}</td>
                    <td className="px-3 py-2">{row.supports ? 'Supports' : 'Conflicts / missing'}</td>
                    <td className="px-3 py-2">{displayValue(row.explanation)}</td>
                    <td className="px-3 py-2">
                      {evidenceId && onOpenEvidence ? (
                        <button type="button" className="text-primary hover:underline" onClick={() => onOpenEvidence(evidenceId)}>
                          {displayValue(citation || evidenceId)}
                        </button>
                      ) : citation && onOpenSourceRecord ? (
                        <button type="button" className="text-primary hover:underline" onClick={() => onOpenSourceRecord(citation)}>
                          {citation}
                        </button>
                      ) : (
                        displayValue(citation)
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {(data.ambiguities.length || data.constraints.length) ? (
        <section className="grid gap-3 md:grid-cols-2">
          <div className="rounded-[12px] border border-border bg-white p-4">
            <h4 className="text-sm font-semibold">Unresolved / open questions</h4>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {data.ambiguities.map((a) => <li key={a}>{a}</li>)}
              {!data.ambiguities.length ? <li className="list-none text-muted">None listed</li> : null}
            </ul>
          </div>
          <div className="rounded-[12px] border border-border bg-white p-4">
            <h4 className="text-sm font-semibold">Constraints</h4>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {data.constraints.map((a) => <li key={a}>{a}</li>)}
              {!data.constraints.length ? <li className="list-none text-muted">None listed</li> : null}
            </ul>
          </div>
        </section>
      ) : null}
    </div>
  );
}
