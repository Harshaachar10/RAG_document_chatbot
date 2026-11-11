import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import { ErrorState } from '../components/ErrorState';
import { Skeleton } from '../components/Skeleton';

type Column = { column: string; role: string; confidence: number; reason: string };
type Profile = {
  source_type: string;
  label?: string;
  filename?: string;
  version?: number;
  status?: string;
  type_reason?: string;
  columns?: Column[];
  excluded_fields?: string[];
  search_routes?: string[];
  rules?: string[];
  validation?: { ok?: boolean; errors?: string[] };
};

export function ProfilesPage() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['source-profiles'],
    queryFn: ({ signal }) => apiFetch<{ items: Profile[] }>('/source-profiles', { signal }),
  });
  const decide = useMutation({
    mutationFn: (profile: Profile) =>
      apiFetch(`/source-profiles/${profile.source_type}/decision`, {
        method: 'POST',
        body: JSON.stringify({ status: 'approved', version: profile.version, reviewer: 'Unassigned', reason: 'Column roles checked.' }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['source-profiles'] }),
  });

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Source Profiles</h1>
        <p className="mt-1 text-sm text-muted">
          The agent proposes column roles from headers and masked samples. A person approves a version before later files of that type reuse it. Synthetic data.
        </p>
      </header>
      {query.isLoading ? <Skeleton className="h-40 w-full" /> : null}
      {query.isError ? <ErrorState message={(query.error as Error).message} onRetry={() => query.refetch()} /> : null}
      <div className="space-y-3">
        {(query.data?.items || []).map((profile) => (
          <article key={`${profile.source_type}-${profile.version}`} className="rounded-[12px] border border-border bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h2 className="text-base font-semibold">{profile.label || profile.source_type}</h2>
                <p className="text-xs text-muted">
                  Version {profile.version ?? 1} · {profile.status || 'proposed'} · {profile.filename}
                </p>
              </div>
              {profile.status !== 'approved' ? (
                <button
                  type="button"
                  className="rounded-md bg-primary px-3 py-1.5 text-sm text-white"
                  onClick={() => decide.mutate(profile)}
                >
                  Approve
                </button>
              ) : (
                <span className="rounded-md bg-emerald-50 px-2 py-1 text-xs text-emerald-800">Approved</span>
              )}
            </div>
            <p className="mt-2 text-sm">{profile.type_reason}</p>
            {profile.rules?.length ? <p className="mt-1 text-sm text-muted">{profile.rules.join(' ')}</p> : null}
            <details className="mt-3">
              <summary className="cursor-pointer text-sm font-medium">Column roles and routes</summary>
              <table className="mt-2 w-full text-sm">
                <thead className="text-left text-xs text-muted">
                  <tr>
                    <th className="py-1">Column</th>
                    <th>Role</th>
                    <th>Confidence</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {(profile.columns || []).map((column) => (
                    <tr key={column.column} className="border-t border-border">
                      <td className="py-1 pr-2">{column.column}</td>
                      <td className="pr-2">{column.role.replaceAll('_', ' ')}</td>
                      <td className="pr-2 tabular-nums">{column.confidence}</td>
                      <td className="text-muted">{column.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-xs text-muted">Routes: {(profile.search_routes || []).join(', ') || 'None'}</p>
              <p className="text-xs text-muted">Excluded: {(profile.excluded_fields || []).join(', ') || 'None'}</p>
            </details>
          </article>
        ))}
      </div>
    </div>
  );
}
