import { useState } from 'react';
import { Dialog } from '../../../components/Dialog';
import { titleCase } from '../../../utils/formatters';

export function DecisionDialog({
  open,
  onOpenChange,
  actions,
  candidates,
  onSubmit,
  submitting,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  actions: string[];
  candidates: Array<Record<string, unknown>>;
  onSubmit: (payload: { action: string; decision: string; selected_doctor_id?: string; comment: string }) => void;
  submitting: boolean;
}) {
  const [action, setAction] = useState(actions[0] || '');
  const [comment, setComment] = useState('');
  const [selected, setSelected] = useState(String(candidates[0]?.candidate_doctor_id || ''));
  const [confirming, setConfirming] = useState(false);

  const needsCandidate = action === 'link_records' || action === 'select_candidate';

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={confirming ? 'Confirm decision' : 'Submit review decision'}
      description="Steward decisions persist in local runtime state. A reason is required for final decisions."
      footer={
        confirming ? (
          <>
            <button type="button" className="rounded-md border border-border px-3 py-2 text-sm" onClick={() => setConfirming(false)} disabled={submitting}>
              Back
            </button>
            <button
              type="button"
              className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              disabled={submitting}
              onClick={() =>
                onSubmit({
                  action,
                  decision: action,
                  selected_doctor_id: needsCandidate ? selected : undefined,
                  comment,
                })
              }
            >
              {submitting ? 'Saving…' : 'Confirm and save'}
            </button>
          </>
        ) : (
          <>
            <button type="button" className="rounded-md border border-border px-3 py-2 text-sm" onClick={() => onOpenChange(false)}>
              Cancel
            </button>
            <button
              type="button"
              className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              disabled={!action || (!comment.trim() && action !== 'resume')}
              onClick={() => setConfirming(true)}
            >
              Continue
            </button>
          </>
        )
      }
    >
      {!confirming ? (
        <div className="space-y-3">
          <label className="block text-sm">
            <span className="text-muted">Action</span>
            <select className="mt-1 w-full rounded-md border border-border px-2 py-2" value={action} onChange={(e) => setAction(e.target.value)}>
              {actions.map((a) => (
                <option key={a} value={a}>{titleCase(a)}</option>
              ))}
            </select>
          </label>
          {needsCandidate ? (
            <label className="block text-sm">
              <span className="text-muted">Selected doctor</span>
              <select className="mt-1 w-full rounded-md border border-border px-2 py-2" value={selected} onChange={(e) => setSelected(e.target.value)}>
                {candidates.map((c) => (
                  <option key={String(c.candidate_doctor_id)} value={String(c.candidate_doctor_id)}>
                    {String(c.doctor_name || c.candidate_doctor_id)}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label className="block text-sm">
            <span className="text-muted">Reason / comment</span>
            <textarea
              className="mt-1 w-full rounded-md border border-border px-2 py-2"
              rows={4}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              required={action !== 'resume'}
            />
          </label>
        </div>
      ) : (
        <div className="space-y-2 text-sm">
          <p><span className="text-muted">Action:</span> {titleCase(action)}</p>
          {needsCandidate ? <p><span className="text-muted">Doctor:</span> {selected}</p> : null}
          <p><span className="text-muted">Reason:</span> {comment || '—'}</p>
        </div>
      )}
    </Dialog>
  );
}
