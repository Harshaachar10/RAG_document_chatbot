import type { ReactNode } from 'react';

export function ChartCard({
  title,
  summary,
  children,
}: {
  title: string;
  summary: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <p className="mt-1 text-xs text-muted">{summary}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}
