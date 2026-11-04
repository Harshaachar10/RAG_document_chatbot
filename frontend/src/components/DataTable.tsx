import type { ReactNode } from 'react';
import { cn } from '../utils/formatters';

export interface Column<T> {
  key: string;
  header: string;
  className?: string;
  render: (row: T) => ReactNode;
}

export function DataTable<T extends { [key: string]: unknown } | object>({
  columns,
  rows,
  onRowClick,
  rowKey,
  dense = false,
  empty,
}: {
  columns: Column<T>[];
  rows: T[];
  onRowClick?: (row: T) => void;
  rowKey: (row: T) => string;
  dense?: boolean;
  empty?: ReactNode;
}) {
  if (!rows.length) {
    return <>{empty}</>;
  }
  return (
    <div className="overflow-auto rounded-[12px] border border-border bg-white shadow-sm">
      <table className="min-w-full border-collapse text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-muted">
          <tr>
            {columns.map((col) => (
              <th key={col.key} className={cn('px-3 py-2 font-semibold', col.className)}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className={cn(
                'border-t border-border',
                onRowClick ? 'cursor-pointer hover:bg-slate-50' : '',
              )}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((col) => (
                <td key={col.key} className={cn(dense ? 'px-3 py-1.5' : 'px-3 py-2.5', col.className)}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
