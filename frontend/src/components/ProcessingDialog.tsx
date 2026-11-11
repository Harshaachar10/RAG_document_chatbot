import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { fetchDemoRun } from '../api/sources';

export function ProcessingDialog({
  runId,
  minimized,
  onMinimized,
  onClose,
}: {
  runId: string | null;
  minimized: boolean;
  onMinimized: (value: boolean) => void;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const query = useQuery({
    queryKey: ['demo-run', runId],
    queryFn: ({ signal }) => fetchDemoRun(runId || '', signal),
    enabled: Boolean(runId),
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 500 : false),
  });
  const run = query.data;
  if (!runId || !run) return null;
  const stages = run.stages || [];
  const done = run.status === 'completed';
  const failed = run.status === 'failed';
  if (minimized && !done) {
    return (
      <button type="button" className="mini" onClick={() => onMinimized(false)}>
        <span className="sp" />
        Cleanup running · {run.progress_percent || 0}%
      </button>
    );
  }
  return (
    <div className="scrim">
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="cleanup-title">
        <div className="modal-h">
          <h2 id="cleanup-title">Running historical cleanup</h2>
          <span className="pill acc">{done ? 'Done' : `${run.progress_percent || 0}%`}</span>
          <button type="button" className="iconbtn x" aria-label="Minimize" onClick={() => onMinimized(true)}>
            –
          </button>
        </div>
        <div className="modal-b">
          <div className="pbar">
            <i style={{ width: `${done ? 100 : run.progress_percent || 0}%` }} />
          </div>
          <div className="stages">
            {stages.map((stage, index) => {
              const finished = index < (run.completed_steps || 0) || done;
              const current = !finished && (run.current_step === stage.key || index === (run.completed_steps || 0));
              return (
                <div key={stage.key} className={`stg ${finished ? 'done' : ''} ${current ? 'run' : ''}`}>
                  <div className="st">{finished ? '✓' : ''}</div>
                  <div>
                    <b>{stage.label}</b>
                    <small>{stage.detail}</small>
                  </div>
                  <div className="cnt">{finished ? stage.detail : ''}</div>
                </div>
              );
            })}
          </div>
          <div className="log" aria-live="polite">
            {stages.slice(0, run.completed_steps || 0).map((stage) => (
              <div key={stage.key}>
                <span className="t">{stage.key}</span>
                {stage.detail}
              </div>
            ))}
            {failed ? <div>{run.errors?.join(' ') || 'The cleanup failed.'}</div> : null}
          </div>
        </div>
        <div className="modal-f">
          {done ? (
            <>
              <div className="result" style={{ flex: 1 }}>
                <button type="button" onClick={() => { onClose(); navigate('/doctors'); }}>
                  <b>Doctors</b>
                  <span>Golden doctors</span>
                </button>
                <button type="button" onClick={() => { onClose(); navigate('/review'); }}>
                  <b>Review</b>
                  <span>Sent to people</span>
                </button>
              </div>
              <button type="button" className="btn primary" onClick={onClose}>
                View dashboard
              </button>
            </>
          ) : (
            <button type="button" className="btn" onClick={() => onMinimized(true)}>
              Minimize
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
