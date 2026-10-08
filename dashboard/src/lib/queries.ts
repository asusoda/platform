import { useQuery } from '@tanstack/react-query';
import { api } from './api';
import type { CiRepo, Overview } from './types';

export function useOverview(prefix: string) {
  return useQuery({
    queryKey: ['overview', prefix],
    queryFn: () => api<Overview>(`/api/dashboard/${prefix}/overview`),
    refetchInterval: 30_000,
    enabled: Boolean(prefix),
  });
}

export function useCi(prefix: string) {
  return useQuery({
    queryKey: ['ci', prefix],
    queryFn: () => api<{ repos: CiRepo[] }>(`/api/dashboard/${prefix}/ci`),
    refetchInterval: 60_000,
    enabled: Boolean(prefix),
  });
}
