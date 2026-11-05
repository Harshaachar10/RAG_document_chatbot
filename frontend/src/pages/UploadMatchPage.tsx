import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
  commitUpload,
  confirmExtract,
  confirmMapping,
  fetchUploadBatches,
  rollbackUpload,
  uploadFile,
} from '../api/uploads';
import { ErrorState } from '../components/ErrorState';
import { Skeleton } from '../components/Skeleton';
import { displayValue } from '../utils/formatters';
import { formatDateTime } from '../utils/dateUtils';

const FLOW = [
  'Upload',
  'File checks',
  'Read and extract',
  'Protect patient data',
  'Map fields',
  'Standardize',
  'Check NPI',
  'Match to master',
  'Check NPPES if needed',
  'Route',
  'Review results',
  'Commit',
];

export function UploadMatchPage() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<'structured' | 'document'>('structured');
  const [batch, setBatch] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mappingJson, setMappingJson] = useState('');
  const [extractJson, setExtractJson] = useState('');

  const history = useQuery({
    queryKey: ['upload-batches'],
    queryFn: ({ signal }) => fetchUploadBatches(signal),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadFile(mode, file),
    onSuccess: (data) => {
      setError(null);
      setBatch(data);
      setMappingJson(JSON.stringify(data.mapping || {}, null, 2));
      setExtractJson(JSON.stringify(data.extracted || {}, null, 2));
      queryClient.invalidateQueries({ queryKey: ['upload-batches'] });
    },
    onError: (err) => setError((err as Error).message),
  });

  async function run(action: () => Promise<Record<string, unknown>>) {
    try {
      setError(null);
      const next = await action();
      setBatch(next);
      queryClient.invalidateQueries({ queryKey: ['upload-batches'] });
      queryClient.invalidateQueries({ queryKey: ['reviews'] });
      queryClient.invalidateQueries({ queryKey: ['doctors'] });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Upload & Match</h1>
        <p className="mt-1 text-sm text-muted">
          Match newly uploaded records and documents against the clean master. The LLM extracts and explains; it does not decide final matches.
        </p>
      </header>

      <ol className="flex flex-wrap gap-2 text-xs" aria-label="Upload processing flow">
        {FLOW.map((step) => (
          <li key={step} className="rounded-md bg-slate-100 px-2 py-1">{step}</li>
        ))}
      </ol>

      <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold">Upload mode</h2>
        <div className="mt-2 flex gap-2">
          <button type="button" className={`rounded-md px-3 py-1.5 text-sm ${mode === 'structured' ? 'bg-primary text-white' : 'bg-slate-100'}`} onClick={() => setMode('structured')}>
            Structured data (CSV / XLSX)
          </button>
          <button type="button" className={`rounded-md px-3 py-1.5 text-sm ${mode === 'document' ? 'bg-primary text-white' : 'bg-slate-100'}`} onClick={() => setMode('document')}>
            Single document (PDF / TXT / image)
          </button>
        </div>
        <label className="mt-4 block text-sm">
          <span className="text-muted">Choose file</span>
          <input
            className="mt-1 block w-full text-sm"
            type="file"
            accept={mode === 'structured' ? '.csv,.xlsx,.xls' : '.pdf,.txt,.png,.jpg,.jpeg'}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadMutation.mutate(file);
            }}
          />
        </label>
        {uploadMutation.isPending ? <p className="mt-2 text-sm text-muted">Uploading and checking…</p> : null}
        {error ? <div className="mt-3"><ErrorState title="Upload issue" message={error} /></div> : null}
      </section>

      {batch ? (
        <section className="space-y-3 rounded-[12px] border border-border bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold">Batch {displayValue(batch.batch_id)}</h2>
              <p className="text-xs text-muted">
                {displayValue(batch.filename)} · {displayValue(batch.status)} · checksum {String(batch.checksum || '').slice(0, 12)}…
              </p>
              {batch.message ? <p className="mt-1 text-sm text-amber-800">{String(batch.message)}</p> : null}
            </div>
            <div className="flex flex-wrap gap-2">
              {batch.mode === 'structured' && batch.status === 'awaiting_confirm' ? (
                <button
                  type="button"
                  className="rounded-md bg-primary px-3 py-1.5 text-sm text-white"
                  onClick={() => run(() => confirmMapping(String(batch.batch_id), JSON.parse(mappingJson || '{}')))}
                >
                  Confirm mapping & match
                </button>
              ) : null}
              {batch.mode === 'document' && batch.status === 'awaiting_confirm' ? (
                <button
                  type="button"
                  className="rounded-md bg-primary px-3 py-1.5 text-sm text-white"
                  onClick={() => run(() => confirmExtract(String(batch.batch_id), JSON.parse(extractJson || '{}')))}
                >
                  Confirm extract & match
                </button>
              ) : null}
              {batch.status === 'matched' ? (
                <button type="button" className="rounded-md bg-primary px-3 py-1.5 text-sm text-white" onClick={() => run(() => commitUpload(String(batch.batch_id)))}>
                  Commit batch
                </button>
              ) : null}
              {batch.committed ? (
                <button type="button" className="rounded-md border border-border px-3 py-1.5 text-sm" onClick={() => run(() => rollbackUpload(String(batch.batch_id)))}>
                  Roll back
                </button>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap gap-2 text-xs">
            {((batch.steps as Array<{ key: string; label: string; status: string }>) || []).map((step) => (
              <span key={step.key} className={`rounded-md px-2 py-1 ${step.status === 'done' ? 'bg-emerald-50 text-emerald-900' : step.status === 'failed' ? 'bg-rose-50 text-rose-900' : 'bg-slate-100'}`}>
                {step.label}: {step.status}
              </span>
            ))}
          </div>

          {batch.mode === 'structured' && batch.status === 'awaiting_confirm' ? (
            <label className="block text-sm">
              <span className="text-muted">Column mapping (edit if needed)</span>
              <textarea className="mt-1 h-40 w-full rounded-md border border-border p-2 font-mono text-xs" value={mappingJson} onChange={(e) => setMappingJson(e.target.value)} />
              <p className="mt-1 text-xs text-muted">Confidence: {displayValue(batch.mapping_confidence)} · Missing required: {JSON.stringify(batch.missing_required || [])}</p>
            </label>
          ) : null}

          {batch.mode === 'document' ? (
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm">
                <span className="text-muted">Redacted source text</span>
                <textarea className="mt-1 h-48 w-full rounded-md border border-border p-2 text-xs" readOnly value={String(batch.redacted_text || '')} />
              </label>
              <label className="block text-sm">
                <span className="text-muted">Extracted values (correct before matching)</span>
                <textarea className="mt-1 h-48 w-full rounded-md border border-border p-2 font-mono text-xs" value={extractJson} onChange={(e) => setExtractJson(e.target.value)} />
              </label>
            </div>
          ) : null}

          {(batch.results as Array<Record<string, unknown>> | undefined)?.length ? (
            <div className="overflow-auto">
              <table className="min-w-full text-sm">
                <thead className="text-xs uppercase text-muted">
                  <tr>
                    <th className="px-2 py-1 text-left">Record</th>
                    <th className="px-2 py-1 text-left">Proposed doctor</th>
                    <th className="px-2 py-1 text-left">NPI</th>
                    <th className="px-2 py-1 text-left">Stated NPI status</th>
                    <th className="px-2 py-1 text-left">Score</th>
                    <th className="px-2 py-1 text-left">Action</th>
                    <th className="px-2 py-1 text-left">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {(batch.results as Array<Record<string, unknown>>).map((row, idx) => {
                    const rec = (row.record || {}) as Record<string, unknown>;
                    const std = (rec.standardized || {}) as Record<string, unknown>;
                    const name = ((std.name || {}) as Record<string, unknown>).display;
                    return (
                      <tr key={idx} className="border-t border-border">
                        <td className="px-2 py-2">{displayValue(name)}</td>
                        <td className="px-2 py-2">{displayValue(row.doctor_name, '—')}</td>
                        <td className="px-2 py-2">{displayValue(row.npi, '—')}</td>
                        <td className="px-2 py-2">{displayValue(row.stated_npi_status)}</td>
                        <td className="px-2 py-2">{row.score == null ? '—' : Number(row.score).toFixed(3)}</td>
                        <td className="px-2 py-2 font-medium">{displayValue(row.action)}</td>
                        <td className="px-2 py-2 text-muted">{displayValue(row.reason)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="mt-2 text-xs text-muted">Action counts: {JSON.stringify(batch.action_counts || {})}</p>
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold">Upload history</h2>
        {history.isLoading ? <Skeleton className="mt-3 h-24 w-full" /> : null}
        <div className="mt-3 overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="text-xs uppercase text-muted">
              <tr>
                <th className="px-2 py-1 text-left">File</th>
                <th className="px-2 py-1 text-left">Type</th>
                <th className="px-2 py-1 text-left">User</th>
                <th className="px-2 py-1 text-left">Time</th>
                <th className="px-2 py-1 text-left">Checksum</th>
                <th className="px-2 py-1 text-left">Status</th>
                <th className="px-2 py-1 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(history.data?.items || []).map((row) => (
                <tr key={String(row.batch_id)} className="border-t border-border">
                  <td className="px-2 py-2">
                    <button type="button" className="text-primary hover:underline" onClick={() => setBatch(row)}>
                      {displayValue(row.filename)}
                    </button>
                  </td>
                  <td className="px-2 py-2">{displayValue(row.mode)}</td>
                  <td className="px-2 py-2">{displayValue(row.uploaded_by)}</td>
                  <td className="px-2 py-2">{formatDateTime(String(row.created_at || ''))}</td>
                  <td className="px-2 py-2 font-mono text-xs">{String(row.checksum || '').slice(0, 12)}</td>
                  <td className="px-2 py-2">{displayValue(row.status)}</td>
                  <td className="px-2 py-2 text-xs">{JSON.stringify(row.action_counts || {})}</td>
                </tr>
              ))}
              {!history.data?.items?.length ? (
                <tr><td className="px-2 py-3 text-muted" colSpan={7}>No uploads yet</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
