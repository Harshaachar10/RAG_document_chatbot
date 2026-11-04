import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { fetchDemoRun, fetchDemoRuns, startDemoRun } from '../../../api/sources';
import { ErrorState } from '../../../components/ErrorState';
import { Skeleton } from '../../../components/Skeleton';
import { formatDateTime } from '../../../utils/dateUtils';

export function ProcessingReplay() {
  const queryClient = useQueryClient();
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const runsQuery = useQuery({
    queryKey: ['demo-runs'],
    queryFn: ({ signal }) => fetchDemoRuns(signal),
  });

  const activeRun = activeRunId
    ? null
    : (runsQuery.data?.items || []).find((r) => r.status === 'running') || (runsQuery.data?.items || [])[0];

  const runId = activeRunId || activeRun?.run_id || null;

  const runQuery = useQuery({
    queryKey: ['demo-run', runId],
    queryFn: ({ signal }) => fetchDemoRun(runId!, signal),
    enabled: !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' || status === 'queued' ? 700 : false;
    },
  });

  useEffect(() => {
    return () => {
      // stop polling on unmount via query unmount
    };
  }, []);

  const startMutation = useMutation({
    mutationFn: () => startDemoRun(),
    onSuccess: (run) => {
      setActiveRunId(run.run_id);
      queryClient.invalidateQueries({ queryKey: ['demo-runs'] });
    },
  });

  const run = runQuery.data || activeRun;

  return (
    <div className="space-y-4">
      <div className="rounded-[12px] border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        Simulation using prepared example outcomes; no live matching or AI service is called.
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          disabled={startMutation.isPending || run?.status === 'running'}
          onClick={() => startMutation.mutate()}
        >
          Replay Processing Demo
        </button>
        <button
          type="button"
          className="rounded-md border border-border px-3 py-2 text-sm"
          onClick={() => {
            runsQuery.refetch();
            if (runId) runQuery.refetch();
          }}
        >
          Refresh job
        </button>
        {run?.status === 'interrupted' || run?.status === 'failed' ? (
          <button
            type="button"
            className="rounded-md border border-border px-3 py-2 text-sm"
            onClick={() => startMutation.mutate()}
          >
            Retry replay
          </button>
        ) : null}
      </div>

      {runsQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
      {startMutation.isError ? <ErrorState message={(startMutation.error as Error).message} /> : null}

      {run ? (
        <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-semibold">{run.run_id}</h3>
            <span className="text-sm capitalize text-muted">{run.status}</span>
          </div>
          <p className="mt-2 text-sm">{run.message}</p>
          <div className="mt-3 h-2 overflow-hidden rounded bg-slate-100" aria-valuenow={run.progress_percent} aria-valuemin={0} aria-valuemax={100} role="progressbar">
            <div className="h-full bg-primary transition-all" style={{ width: `${run.progress_percent}%` }} />
          </div>
          <p className="mt-2 text-xs text-muted">
            Step {run.completed_steps}/{run.total_steps}: {run.current_step} · Updated {formatDateTime(run.updated_at)}
          </p>
          <ol className="mt-4 space-y-1 text-sm">
            {(run.step_labels || []).map((label, idx) => (
              <li key={label} className={idx < run.completed_steps ? 'font-medium text-foreground' : 'text-muted'}>
                {idx + 1}. {label}
              </li>
            ))}
          </ol>
          {run.result_counts ? (
            <div className="mt-4 grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
              {Object.entries(run.result_counts).map(([k, v]) => (
                <div key={k} className="rounded-md bg-slate-50 px-3 py-2">
                  <div className="text-xs text-muted">{k}</div>
                  <div className="font-semibold">{v}</div>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      ) : (
        <p className="text-sm text-muted">No processing runs available.</p>
      )}
    </div>
  );
}
