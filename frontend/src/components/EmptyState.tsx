export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="rounded-[12px] border border-dashed border-border bg-white px-6 py-10 text-center">
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      {description ? <p className="mt-2 text-sm text-muted">{description}</p> : null}
    </div>
  );
}
