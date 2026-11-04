import { Link } from 'react-router-dom';
import { EmptyState } from '../../../components/EmptyState';
import { formatDateTime } from '../../../utils/dateUtils';
import { displayValue } from '../../../utils/formatters';

export function ReviewHistory({ items }: { items: Array<Record<string, unknown>> }) {
  if (!items.length) return <EmptyState title="No review history yet" />;
  return (
    <div className="overflow-auto rounded-[12px] border border-border bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-muted">
          <tr>
            <th className="px-3 py-2 text-left">Timestamp</th>
            <th className="px-3 py-2 text-left">Case</th>
            <th className="px-3 py-2 text-left">Action</th>
            <th className="px-3 py-2 text-left">Reviewer</th>
            <th className="px-3 py-2 text-left">Reason</th>
            <th className="px-3 py-2 text-left">Source</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={String(row.audit_id)} className="border-t border-border">
              <td className="px-3 py-2">{formatDateTime(String(row.occurred_at || ''))}</td>
              <td className="px-3 py-2">
                {row.review_id ? (
                  <Link className="text-primary hover:underline" to={`/reviews/${String(row.review_id)}`}>
                    {String(row.review_id)}
                  </Link>
                ) : '—'}
              </td>
              <td className="px-3 py-2">{displayValue(row.action)}</td>
              <td className="px-3 py-2">{displayValue(row.actor_label)}</td>
              <td className="px-3 py-2">{displayValue(row.summary)}</td>
              <td className="px-3 py-2">
                {row.is_seeded ? (
                  <span className="text-xs text-muted" title="Seeded historical sample event">Sample history</span>
                ) : (
                  <span className="text-xs text-emerald-800">Live decision</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
