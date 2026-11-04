import type { MatchExplanation as Match } from '../../../api/contracts';
import { displayValue } from '../../../utils/formatters';

export function MatchExplanation({ data }: { data: Match }) {
  return (
    <div className="space-y-4">
      <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold">Decision summary</h3>
        <p className="mt-2 text-sm">{data.summary}</p>
        <div className="mt-3 rounded-md border border-sky-200 bg-sky-50 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-sky-900">{data.label || 'Prepared result'}</div>
          <p className="mt-1 text-sm text-sky-950">{data.simulated_recommendation}</p>
        </div>
        <dl className="mt-3 grid gap-2 text-sm md:grid-cols-3">
          <div><dt className="text-muted">Match score</dt><dd className="font-medium">{data.demo_match_score ?? '—'}</dd></div>
          <div><dt className="text-muted">Decision method</dt><dd className="font-medium">{displayValue(data.decision_method)}</dd></div>
          <div><dt className="text-muted">Review status</dt><dd className="font-medium">{displayValue(data.review_status, 'n/a')}</dd></div>
        </dl>
      </section>

      {data.side_by_side.length ? (
        <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold">Side-by-side comparison</h3>
          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {data.side_by_side.map((row, idx) => (
              <div key={idx} className="rounded-md border border-border p-3 text-sm">
                {Object.entries(row).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-2 border-b border-border py-1 last:border-0">
                    <span className="text-muted">{k}</span>
                    <span>{displayValue(v)}</span>
                  </div>
                ))}
              </div>
            ))}
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
              {(data.evidence_rows || []).map((row, idx) => (
                <tr key={idx} className="border-t border-border">
                  <td className="px-3 py-2">{displayValue(row.observation)}</td>
                  <td className="px-3 py-2">{row.supports ? 'Supports' : 'Conflicts / missing'}</td>
                  <td className="px-3 py-2">{displayValue(row.explanation)}</td>
                  <td className="px-3 py-2">{displayValue(row.citation)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {(data.ambiguities.length || data.constraints.length) ? (
        <section className="grid gap-3 md:grid-cols-2">
          <div className="rounded-[12px] border border-border bg-white p-4">
            <h4 className="text-sm font-semibold">Ambiguities</h4>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {data.ambiguities.map((a) => <li key={a}>{a}</li>)}
            </ul>
          </div>
          <div className="rounded-[12px] border border-border bg-white p-4">
            <h4 className="text-sm font-semibold">Constraints</h4>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {data.constraints.map((a) => <li key={a}>{a}</li>)}
            </ul>
          </div>
        </section>
      ) : null}
    </div>
  );
}
