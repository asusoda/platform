import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, api, send } from './api';
import type {
  Branding,
  CiRepo,
  IntegrationList,
  ModuleState,
  NotificationList,
  OrganizationDetail,
  Overview,
  SentryIssues,
  Trends,
} from './types';

export function useOverview(prefix: string) {
  return useQuery({
    queryKey: ['overview', prefix],
    queryFn: () => api<Overview>(`/api/dashboard/${prefix}/overview`),
    refetchInterval: 30_000,
    enabled: Boolean(prefix),
  });
}

export function useTrends(prefix: string, days: number) {
  return useQuery({
    queryKey: ['overview', prefix, 'trends', days],
    queryFn: () => api<Trends>(`/api/dashboard/${prefix}/trends?days=${days}`),
    refetchInterval: 300_000,
    enabled: Boolean(prefix),
    placeholderData: (previous) => previous,
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

export function useSentryIssues(prefix: string) {
  return useQuery({
    queryKey: ['errors', prefix],
    queryFn: () => api<SentryIssues>(`/api/dashboard/${prefix}/errors?limit=50`),
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

// One organization with its settings.
export function useOrganization(id: number | undefined) {
  return useQuery({
    queryKey: ['organization', id],
    queryFn: () => api<OrganizationDetail>(`/api/organizations/${id}`),
    enabled: id !== undefined,
  });
}

export function useModules(id: number | undefined) {
  return useQuery({
    queryKey: ['modules', id],
    queryFn: () => api<{ modules: ModuleState[] }>(`/api/organizations/${id}/modules`),
    enabled: id !== undefined,
  });
}

// Whether an error is the API saying the Discord bot cannot be reached.
export function isBotDown(error: unknown): boolean {
  return error instanceof ApiError && error.status === 503;
}

export function useNotifications(prefix: string) {
  return useQuery({
    queryKey: ['notifications', prefix],
    queryFn: () => api<NotificationList>(`/api/dashboard/${prefix}/notifications`),
    refetchInterval: 60_000,
    enabled: Boolean(prefix),
  });
}

// Resolve or reopen notifications by id. The answer is the new list, so the bell and the page update at once.
export function useNotificationChange(prefix: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ action, ids }: { action: 'resolve' | 'reopen'; ids: string[] }) =>
      send<NotificationList>(`/api/dashboard/${prefix}/notifications/${action}`, 'POST', { ids }),
    onSuccess: (list) => {
      client.setQueryData(['notifications', prefix], list);
      client.invalidateQueries({ queryKey: ['overview', prefix] });
    },
  });
}

export function useIntegrations(prefix: string) {
  return useQuery({
    queryKey: ['integrations', prefix],
    queryFn: () => api<IntegrationList>(`/api/dashboard/${prefix}/integrations`),
    enabled: Boolean(prefix),
    staleTime: 60_000,
  });
}
