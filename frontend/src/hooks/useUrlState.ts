import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

export function useUrlState() {
  const [params, setParams] = useSearchParams();

  const get = useCallback((key: string, fallback = '') => params.get(key) ?? fallback, [params]);

  const setMany = useCallback(
    (updates: Record<string, string | null | undefined>, replace = false) => {
      const next = new URLSearchParams(params);
      Object.entries(updates).forEach(([key, value]) => {
        if (value === null || value === undefined || value === '') next.delete(key);
        else next.set(key, value);
      });
      setParams(next, { replace });
    },
    [params, setParams],
  );

  const values = useMemo(() => Object.fromEntries(params.entries()), [params]);
  return { params, get, setMany, values };
}
