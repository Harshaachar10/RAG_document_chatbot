import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { fetchAiJob } from '../../api/ai';
import type { AiJob } from '../../api/contracts';

const TERMINAL = new Set(['completed', 'failed', 'interrupted']);

export function jobStorageKey(scope: string) {
  return `doctor-intel-ai:${scope}`;
}

export function useAiJob(scope: string) {
  const [jobId, setJobId] = useState<string | null>(() => {
    if (typeof sessionStorage === 'undefined') return null;
    return sessionStorage.getItem(jobStorageKey(scope));
  });

  useEffect(() => {
    if (typeof sessionStorage === 'undefined') return;
    if (jobId) sessionStorage.setItem(jobStorageKey(scope), jobId);
  }, [jobId, scope]);

  const query = useQuery({
    queryKey: ['ai-job', jobId],
    enabled: !!jobId,
    queryFn: ({ signal }) => fetchAiJob(jobId as string, signal),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (!status || TERMINAL.has(status)) return false;
      return 1500;
    },
  });

  const busy = !!query.data && !TERMINAL.has(query.data.status);
  return {
    jobId,
    setJobId,
    job: query.data as AiJob | undefined,
    error: query.error as Error | null,
    busy,
    isFetching: query.isFetching,
  };
}
