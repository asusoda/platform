import { type QueryClient, queryOptions, useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import type { PointEntry, PointsMember } from '../../lib/types';

export type EventGroup = { event: string; entries: PointEntry[]; total: number; last: string | null };

export const entryCount = (n: number) => (n === 1 ? '1 entry' : `${n} entries`);
export const signed = (n: number) => `${n > 0 ? '+' : ''}${Number.isInteger(n) ? n : n.toFixed(1)}`;
export const memberKey = (m: { email: string | null; uuid?: string }) => m.email ?? m.uuid ?? '';

export const pointsMembersQuery = (prefix: string) =>
  queryOptions({
    queryKey: ['points', prefix, 'members'],
    queryFn: () => api<{ total_users: number; users: PointsMember[] }>(`/api/points/${prefix}/users`),
    enabled: Boolean(prefix),
  });

export const pointsEntriesQuery = (prefix: string) =>
  queryOptions({
    queryKey: ['points', prefix, 'entries'],
    queryFn: () => api<PointEntry[]>(`/api/points/${prefix}/get_points`),
    enabled: Boolean(prefix),
  });

// Starts both Points requests, for a sidebar hover or before the module check of the page answers.
export function prefetchPoints(client: QueryClient, prefix: string) {
  void client.prefetchQuery(pointsMembersQuery(prefix));
  void client.prefetchQuery(pointsEntriesQuery(prefix));
}

export function usePoints(prefix: string) {
  const members = useQuery(pointsMembersQuery(prefix));
  const entries = useQuery(pointsEntriesQuery(prefix));
  return { members, entries };
}
