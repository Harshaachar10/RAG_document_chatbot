import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { documentDownloadUrl, fetchDocument, fetchEvidence } from '../../../api/evidence';
import { EmptyState } from '../../../components/EmptyState';
import { ErrorState } from '../../../components/ErrorState';
import { Skeleton } from '../../../components/Skeleton';
import { formatDate } from '../../../utils/dateUtils';
import { displayValue } from '../../../utils/formatters';

export function EvidenceWorkspace({
  evidenceId,
  onBack,
}: {
  evidenceId?: string | null;
  onBack?: () => void;
}) {
  const evidQuery = useQuery({
    queryKey: ['evidence', evidenceId],
    queryFn: ({ signal }) => fetchEvidence(evidenceId!, signal),
    enabled: !!evidenceId,
  });

  const documentId = evidQuery.data?.document_id;
  const documentVersion = evidQuery.data?.document_version;
  const docQuery = useQuery({
    queryKey: ['document', documentId, documentVersion],
    queryFn: ({ signal }) => fetchDocument(documentId!, signal, documentVersion),
    enabled: !!documentId,
  });

  const [pageIndex, setPageIndex] = useState(0);
  useEffect(() => {
    if (evidQuery.data?.page_number) {
      setPageIndex(Math.max(0, (evidQuery.data.page_number || 1) - 1));
    } else {
      setPageIndex(0);
    }
  }, [evidQuery.data?.evidence_id, evidQuery.data?.page_number]);

  if (!evidenceId) {
    return <EmptyState title="Select evidence" description="Choose a citation to preview the source document or CSV row." />;
  }
  if (evidQuery.isLoading) return <Skeleton className="h-64 w-full" />;
  if (evidQuery.isError) {
    return <ErrorState message={(evidQuery.error as Error).message} onRetry={() => evidQuery.refetch()} />;
  }
  const evid = evidQuery.data!;

  if (evid.preview_kind === 'source_row') {
    const fields = (evid.source_row?.fields || {}) as Record<string, unknown>;
    return (
      <div className="space-y-3">
        {onBack ? (
          <button type="button" className="text-sm text-primary hover:underline md:hidden" onClick={onBack}>Back</button>
        ) : null}
        <div className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
          <h3 className="font-semibold">Source row evidence</h3>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between gap-4"><dt className="text-muted">Source record</dt><dd>{displayValue(evid.source_record_id)}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-muted">Snapshot</dt><dd>{displayValue(evid.source_snapshot)}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-muted">Field</dt><dd>{displayValue(evid.source_field)}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-muted">Quoted value</dt><dd className="font-medium">{displayValue(evid.quoted_text)}</dd></div>
          </dl>
          <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm">
            {Object.entries(fields).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3 border-b border-border py-1 last:border-0">
                <span className="text-muted">{k}</span>
                <span className={k === evid.source_field ? 'font-semibold text-primary' : ''}>{displayValue(v)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (docQuery.isLoading) return <Skeleton className="h-64 w-full" />;
  if (docQuery.isError) return <ErrorState message={(docQuery.error as Error).message} onRetry={() => docQuery.refetch()} />;
  const doc = docQuery.data!;
  const page = doc.pages[pageIndex] || doc.pages[0];

  return (
    <div className="space-y-3">
      {onBack ? (
        <button type="button" className="text-sm text-primary hover:underline md:hidden" onClick={onBack}>Back</button>
      ) : null}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-semibold">{doc.title}</h3>
          <p className="text-xs text-muted">
            {doc.document_type} · {formatDate(doc.document_date)} · v{doc.version}
          </p>
        </div>
        <a
          className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-slate-50"
          href={documentDownloadUrl(doc.document_id)}
        >
          Download .txt
        </a>
      </div>
      <div className="rounded-[12px] border border-border bg-[#fbfaf7] p-5 shadow-sm">
        <div className="mb-4 border-b border-border pb-3">
          <div className="text-xs uppercase tracking-wide text-muted">{page?.label || `Page ${page?.page_number}`}</div>
          <div className="mt-1 text-xs text-muted">
            Submitted by {displayValue(doc.submitted_by, 'Not recorded')} to {displayValue(doc.submitted_to, 'Not recorded')}
          </div>
        </div>
        <div className="space-y-3">
          {(page?.blocks || []).map((block) => {
            const highlight = evid.block_id === block.block_id || (evid.quoted_text && block.text.includes(evid.quoted_text));
            return (
              <p
                key={block.block_id}
                className={`text-sm leading-relaxed ${block.kind === 'heading' ? 'text-base font-semibold' : ''} ${
                  highlight ? 'rounded bg-amber-100 px-1 py-0.5' : ''
                }`}
              >
                {block.text}
              </p>
            );
          })}
        </div>
      </div>
      <div className="flex items-center justify-between">
        <button
          type="button"
          className="rounded-md border border-border px-3 py-1.5 text-sm disabled:opacity-40"
          disabled={pageIndex <= 0}
          onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
        >
          Previous page
        </button>
        <span className="text-xs text-muted">
          Page {pageIndex + 1} of {doc.pages.length}
        </span>
        <button
          type="button"
          className="rounded-md border border-border px-3 py-1.5 text-sm disabled:opacity-40"
          disabled={pageIndex >= doc.pages.length - 1}
          onClick={() => setPageIndex((p) => Math.min(doc.pages.length - 1, p + 1))}
        >
          Next page
        </button>
      </div>
      {evid.quoted_text ? (
        <p className="text-sm"><span className="text-muted">Citation:</span> “{evid.quoted_text}”</p>
      ) : null}
    </div>
  );
}
