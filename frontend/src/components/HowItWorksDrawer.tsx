import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import { fetchHealth } from '../api/dashboard';
import { Drawer } from './Drawer';
import { ProfilesPage } from '../pages/ProfilesPage';
import { QualityPage } from '../pages/QualityPage';
import { RunsPage } from '../pages/RunsPage';

const TABS = [
  { id: 'privacy', label: 'Privacy' },
  { id: 'profiles', label: 'Source profiles' },
  { id: 'runs', label: 'Cleanup runs' },
  { id: 'quality', label: 'Search quality' },
  { id: 'scorecard', label: 'Accuracy scorecard' },
  { id: 'audit', label: 'Audit log' },
] as const;

export function HowItWorksDrawer({
  open,
  tab,
  onTab,
  onOpenChange,
}: {
  open: boolean;
  tab: string;
  onTab: (tab: string) => void;
  onOpenChange: (open: boolean) => void;
}) {
  const health = useQuery({ queryKey: ['health'], queryFn: ({ signal }) => fetchHealth(signal) });
  const notes = useQuery({
    queryKey: ['privacy-note'],
    queryFn: ({ signal }) => apiFetch<{ items: Array<Record<string, unknown>> }>('/notes/insights?page_size=1', { signal }),
    enabled: open && tab === 'privacy',
  });
  const note = notes.data?.items?.[0];

  return (
    <Drawer open={open} onOpenChange={onOpenChange} title="How it works">
      <div className="space-y-4 p-4">
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="How it works">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              className={`rounded-md px-3 py-1.5 text-sm ${tab === item.id ? 'bg-primary text-white' : 'bg-slate-100'}`}
              onClick={() => onTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        {tab === 'privacy' ? (
          <div className="grid gap-3 md:grid-cols-2">
            <section className="rounded-[12px] border border-border bg-white p-3">
              <h2 className="text-sm font-semibold">Redacted note</h2>
              <p className="mt-2 text-sm">{String(note?.redacted_note || 'No note is stored yet.')}</p>
            </section>
            <section className="rounded-[12px] border border-border bg-slate-50 p-3">
              <h2 className="text-sm font-semibold">Where models run</h2>
              <p className="mt-2 text-sm">
                Chat and embeddings use the private Azure OpenAI endpoint named in configuration. The service is not asked to retain prompts.
                {health.data?.search_mode === 'local'
                  ? ' Semantic search is running locally (test mode).'
                  : ' Semantic search is using Azure AI Search.'}
              </p>
              <p className="mt-2 text-xs text-muted">Synthetic data. Patient fields are removed before any model call.</p>
            </section>
          </div>
        ) : null}
        {tab === 'profiles' ? <ProfilesPage /> : null}
        {tab === 'runs' ? <RunsPage /> : null}
        {tab === 'quality' ? <QualityPage /> : null}
        {tab === 'scorecard' ? (
          <section className="rounded-[12px] border border-border bg-white p-4 text-sm">
            <h2 className="text-sm font-semibold">Accuracy scorecard</h2>
            <p className="mt-2">No answer key is loaded, so precision and recall are not shown.</p>
            <p className="mt-2 text-xs text-muted">When data/answer_key exists, a separate script measures this label: Measured on synthetic data.</p>
          </section>
        ) : null}
        {tab === 'audit' ? <QualityPage /> : null}
      </div>
    </Drawer>
  );
}
