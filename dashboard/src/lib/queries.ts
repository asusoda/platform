import { useQuery } from '@tanstack/react-query';
import { ApiError, api } from './api';
import type { Branding, CiRepo, Overview } from './types';

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

export function useBranding(prefix: string) {
  return useQuery({
    queryKey: ['branding', prefix],
    queryFn: () => api<Branding>(`/api/dashboard/${prefix}/branding`),
    enabled: Boolean(prefix),
    staleTime: 300_000,
  });
}

// Whether the signed-in officer is the superadmin. A 403 means no.
export function useSuperadmin() {
  return useQuery({
    queryKey: ['superadmin'],
    queryFn: () =>
      api<{ is_superadmin: boolean }>('/api/superadmin/check').then(
        (body) => body.is_superadmin,
        (error) => {
          if (error instanceof ApiError && error.status === 403) return false;
          throw error;
        },
      ),
    retry: false,
    staleTime: 600_000,
  });
}
