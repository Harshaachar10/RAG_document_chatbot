import type { ReactNode } from 'react';

export function FilterBar({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-[12px] border border-border bg-white p-3 shadow-sm">
      {children}
    </div>
  );
}

export function FilterField({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="flex min-w-[140px] flex-col gap-1 text-xs font-medium text-muted">
      {label}
      {children}
    </label>
  );
}

export const inputClass =
  'rounded-md border border-border bg-white px-2.5 py-2 text-sm text-foreground shadow-sm focus:border-primary';
