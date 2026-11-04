import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-lg rounded-[12px] border border-border bg-white p-8 text-center shadow-sm">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="mt-2 text-sm text-muted">The route you requested is not part of Doctor Intelligence.</p>
      <Link to="/overview" className="mt-4 inline-block rounded-md bg-primary px-3 py-2 text-sm font-medium text-white">
        Back to Overview
      </Link>
    </div>
  );
}
