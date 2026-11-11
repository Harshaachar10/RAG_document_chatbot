import { useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from '../api/client';

type Citation = { label: string; href: string };
type AskResponse = { answer: string; citations: Citation[]; tools: Array<{ name: string; filters: Record<string, unknown> }>; wrote: boolean };

const SUGGESTIONS = [
  'Which doctors changed practice in the last 6 months?',
  'Show payments over $1,000 with a doubtful identity.',
  'Which records for Dr. Sharma are still unresolved?',
  'Why are the two Sarah Lees separate?',
];

export function AskPanel({ doctorId, title = 'Ask' }: { doctorId?: string; title?: string }) {
  const [question, setQuestion] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);

  async function submit(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    setPending(true);
    setError(null);
    try {
      const body = await apiFetch<AskResponse>('/ask', {
        method: 'POST',
        body: JSON.stringify({ question: trimmed, doctor_id: doctorId || null }),
      });
      setResult(body);
      setQuestion(trimmed);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The assistant could not answer.');
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="rounded-[12px] border border-border bg-white p-4">
      <h2 className="text-sm font-semibold">{title}</h2>
      <p className="mt-1 text-xs text-muted">Read only. Answers cite stored doctors and records. Synthetic data.</p>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void submit(question);
        }}
      >
        <label className="sr-only" htmlFor={doctorId ? `ask-${doctorId}` : 'ask-dashboard'}>
          Question
        </label>
        <input
          id={doctorId ? `ask-${doctorId}` : 'ask-dashboard'}
          className="min-w-0 flex-1 rounded-md border border-border px-3 py-2 text-sm"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about stored doctors, payments, or unresolved records"
        />
        <button type="submit" className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white" disabled={pending}>
          {pending ? 'Asking…' : 'Ask'}
        </button>
      </form>
      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((item) => (
          <button key={item} type="button" className="rounded-full border border-border px-2 py-1 text-xs" onClick={() => void submit(item)}>
            {item}
          </button>
        ))}
      </div>
      {error ? <p className="mt-3 text-sm text-rose-800">{error}</p> : null}
      {result ? (
        <div className="mt-3 text-sm">
          <p>{result.answer}</p>
          {result.citations?.length ? (
            <ul className="mt-2 flex flex-wrap gap-2">
              {result.citations.map((cite) => (
                <li key={cite.href + cite.label}>
                  <Link className="text-primary underline" to={cite.href}>
                    {cite.label}
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
          <details className="mt-2">
            <summary className="cursor-pointer text-xs text-muted">How I answered</summary>
            <ul className="mt-1 text-xs text-muted">
              {(result.tools || []).map((tool) => (
                <li key={tool.name}>
                  {tool.name} {Object.keys(tool.filters || {}).length ? JSON.stringify(tool.filters) : ''}
                </li>
              ))}
              {(result.tools || []).length === 0 ? <li>No lookup was needed.</li> : null}
            </ul>
          </details>
        </div>
      ) : null}
    </section>
  );
}
