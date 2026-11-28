import { type QueryClient, queryOptions, useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import type { PointEntry, PointsHistory, PointsImport, PointsMember } from '../../lib/types';

// Points that an agent, the bot or a CSV import adds show within this time. An unchanged list answers 304.
export const POINTS_REFETCH_MS = 15_000;
// How often an import that runs asks for its progress.
export const IMPORT_POLL_MS = 2_000;

export type MembersBody = { total_users: number; users: PointsMember[] };

export type EventGroup = { event: string; entries: PointEntry[]; total: number; last: string | null };

export const entryCount = (n: number) => (n === 1 ? '1 entry' : `${n} entries`);
export const signed = (n: number) => `${n > 0 ? '+' : ''}${Number.isInteger(n) ? n : n.toFixed(1)}`;
export const memberKey = (m: { email: string | null; uuid?: string }) => m.email ?? m.uuid ?? '';

export const pointsMembersQuery = (prefix: string) =>
  queryOptions({
    queryKey: ['points', prefix, 'members'],
    queryFn: () => api<MembersBody>(`/api/points/${prefix}/users`),
    enabled: Boolean(prefix),
    refetchInterval: POINTS_REFETCH_MS,
  });

export const pointsEntriesQuery = (prefix: string) =>
  queryOptions({
    queryKey: ['points', prefix, 'entries'],
    queryFn: () => api<PointEntry[]>(`/api/points/${prefix}/get_points`),
    enabled: Boolean(prefix),
    refetchInterval: POINTS_REFETCH_MS,
  });

// True while an import run is queued or running.
export const importRunning = (run: PointsImport | undefined) => run?.status === 'queued' || run?.status === 'running';

// One CSV import run. It asks again every IMPORT_POLL_MS until the run is done or failed.
export const pointsImportQuery = (prefix: string, id: number | null) =>
  queryOptions({
    queryKey: ['points', prefix, 'imports', id],
    queryFn: () => api<PointsImport>(`/api/points/${prefix}/imports/${id}`),
    enabled: Boolean(prefix) && id !== null,
    refetchInterval: (query) => (!query.state.data || importRunning(query.state.data) ? IMPORT_POLL_MS : false),
  });

// The newest CSV import runs. It asks again while one runs.
export const pointsImportsQuery = (prefix: string) =>
  queryOptions({
    queryKey: ['points', prefix, 'imports'],
    queryFn: () => api<{ imports: PointsImport[] }>(`/api/points/${prefix}/imports`),
    enabled: Boolean(prefix),
    refetchInterval: (query) => (query.state.data?.imports.some(importRunning) ? IMPORT_POLL_MS : POINTS_REFETCH_MS),
  });

// Loads again every page that shows a points total: Points, Overview, Store and the member store.
export function refreshPoints(client: QueryClient, prefix: string) {
  for (const area of ['points', 'overview', 'store', 'member-store']) void client.invalidateQueries({ queryKey: [area, prefix] });
}

// Adds points to the members in the cached list at once, so a total moves before the refetch answers.
export function addToTotals(client: QueryClient, prefix: string, keys: string[], points: number) {
  const wanted = new Set(keys.map((k) => k.toLowerCase()));
  client.setQueryData<MembersBody>(['points', prefix, 'members'], (body) =>
    body
      ? {
          ...body,
          users: body.users.map((m) =>
            [m.email, m.username, m.uuid].some((k) => k && wanted.has(k.toLowerCase())) ? { ...m, points: m.points + points } : m,
          ),
        }
      : body,
  );
}

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

export type MemberDraft = { name: string; asu_id: string; academic_standing: string; major: string };

// The fields of the draft that differ from the member. An empty field is null, so no member gets an empty student id.
export function memberChanges(member: Partial<Record<keyof MemberDraft, string | null>>, draft: MemberDraft) {
  const changes: Partial<Record<keyof MemberDraft, string | null>> = {};
  for (const key of Object.keys(draft) as (keyof MemberDraft)[]) {
    const value = draft[key].trim() || null;
    if (value !== (member[key] || null)) changes[key] = value;
  }
  return changes;
}

export type HistoryEntry = PointsHistory['points_history'][number];
// The entries of one event, or of one store order (its purchase and refunds), newest first.
export type EntryGroup = { key: string; label: string; order: number | null; entries: HistoryEntry[]; total: number; last: string | null };

const ORDER_EVENT = /^(?:Storefront Purchase|Refund) - Order #(\d+)$/;

// A member's entries grouped by event, newest group first. A store order and its refund make one group.
export function groupEntries(entries: HistoryEntry[]): EntryGroup[] {
  const groups = new Map<string, EntryGroup>();
  for (const e of entries) {
    const order = e.event ? ORDER_EVENT.exec(e.event)?.[1] : undefined;
    const key = order ? `order:${order}` : `event:${e.event ?? ''}`;
    const label = order ? `Order #${order}` : (e.event ?? 'No event');
    const g = groups.get(key) ?? { key, label, order: order ? Number(order) : null, entries: [], total: 0, last: null };
    g.entries.push(e);
    g.total += e.points;
    if (e.timestamp && (!g.last || e.timestamp > g.last)) g.last = e.timestamp;
    groups.set(key, g);
  }
  for (const g of groups.values()) g.entries.sort((a, b) => (b.timestamp ?? '').localeCompare(a.timestamp ?? ''));
  return [...groups.values()].sort((a, b) => (b.last ?? '').localeCompare(a.last ?? ''));
}

// The sum of positive points given since the time, such as 30 days ago.
export const givenSince = (entries: { points: number; timestamp: string | null }[], since: number) =>
  entries.filter((e) => e.points > 0 && e.timestamp && new Date(e.timestamp).getTime() >= since).reduce((n, e) => n + e.points, 0);
