import { displayValue } from '../../../utils/formatters';

export function RecommendationPanel({ recommendation }: { recommendation: Record<string, unknown> }) {
  const label = String(recommendation.label || 'Prepared result');
  return (
    <section className="rounded-[12px] border border-sky-200 bg-sky-50 p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-sky-900">{label}</div>
      <p className="mt-2 text-sm text-sky-950">
        {displayValue(recommendation.summary || recommendation.simulated_recommendation)}
      </p>
      {recommendation.demo_match_score !== undefined && recommendation.demo_match_score !== null ? (
        <p className="mt-2 text-xs text-sky-900">Demo match score: {String(recommendation.demo_match_score)}</p>
      ) : null}
    </section>
  );
}
