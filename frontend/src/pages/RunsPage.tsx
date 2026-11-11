import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import { ErrorState } from '../components/ErrorState';
import { Skeleton } from '../components/Skeleton';

type Round = { round: number; linked: number; new_values?: number; reviews?: number; stop_reason?: string };
type Decision = { record_id?: string; action?: string; target_label?: string; route?: string; found_by?: string[]; score?: number; learned_value?: boolean };

export function RunsPage() {
  const [openRound, setOpenRound] = useState<number | null>(null);
  const runs = useQuery({
    queryKey: ['cleanup-runs'],
    queryFn: ({ signal }) => apiFetch<{ rounds: Round[]; search: Record<string, number | string>; embedding: Record<string, string | number> }>('/cleanup/runs', { signal }),
  });
  const detail = useQuery({
    queryKey: ['cleanup-round', openRound],
    queryFn: ({ signal }) => apiFetch<{ decisions: Decision[]; total: number }>(`/cleanup/rounds/${openRound}`, { signal }),
    enabled: openRound !== null,
  });

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Cleanup Runs</h1>
        <p className="mt-1 text-sm text-muted">Round-by-round links and values learned. Synthetic data.</p>
      </header>
      {runs.isLoading ? <Skeleton className="h-40 w-full" /> : null}
      {runs.isError ? <ErrorState message={(runs.error as Error).message} onRetry={() => runs.refetch()} /> : null}
      <div className="overflow-auto rounded-[12px] border border-border bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-muted">
            <tr>
              <th className="px-3 py-2">Round</th>
              <th className="px-3 py-2">Records linked</th>
              <th className="px-3 py-2">New values</th>
              <th className="px-3 py-2">Reviews</th>
              <th className="px-3 py-2">Stop reason</th>
            </tr>
          </thead>
          <tbody>
            {(runs.data?.rounds || []).map((round) => (
              <tr key={round.round} className="border-t border-border">
                <td className="px-3 py-2">
                  <button type="button" className="text-primary hover:underline" onClick={() => setOpenRound(round.round)}>
                    Round {round.round}
                  </button>
                </td>
                <td className="px-3 py-2 tabular-nums">{round.linked}</td>
                <td className="px-3 py-2 tabular-nums">{round.new_values ?? 0}</td>
                <td className="px-3 py-2 tabular-nums">{round.reviews ?? 0}</td>
                <td className="px-3 py-2 text-muted">{round.stop_reason || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {openRound !== null ? (
        <section className="rounded-[12px] border border-border bg-white p-4" aria-live="polite">
          <h2 className="text-sm font-semibold">Round {openRound}</h2>
          {detail.isLoading ? <Skeleton className="mt-2 h-20 w-full" /> : null}
          <ul className="mt-2 max-h-80 divide-y divide-border overflow-auto text-sm">
            {(detail.data?.decisions || []).slice(0, 40).map((decision) => (
              <li key={decision.record_id} className="py-2">
                <span className="font-medium">{decision.record_id}</span>
                <span className="text-muted"> → {decision.target_label || decision.action}</span>
                <span className="mt-0.5 block text-xs text-muted">
                  {(decision.found_by || []).join(' and ') || 'filter'} · {decision.route || 'route not recorded'}
                  {decision.learned_value ? ' · learned value' : ''}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <p className="text-xs text-muted">
        Semantic search: {String(runs.data?.embedding?.status || runs.data?.search?.semantic_status || 'skipped')}
      </p>
    </div>
  );
}
