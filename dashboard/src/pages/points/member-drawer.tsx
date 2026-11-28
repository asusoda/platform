import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pencil, Plus } from 'lucide-react';
import { useMemo } from 'react';
import { Badge, Button, cx, DeleteButton, Drawer, ErrorNote, SkeletonRows } from '../../components/ui';
import { api, send } from '../../lib/api';
import { compact, timeAgo } from '../../lib/format';
import type { PointsHistory, PointsMember } from '../../lib/types';
import { type EntryGroup, entryCount, givenSince, groupEntries, memberKey, POINTS_REFETCH_MS, refreshPoints, signed } from './shared';

const DAY_MS = 86_400_000;

// One member on the Points page: the live total, the points of the last 30 days and the entries by event.
// The total comes from the member list, so an award or a refetch of the list changes it at once.
export function MemberDrawer({
  prefix,
  member,
  onClose,
  onEdit,
  onAward,
}: {
  prefix: string;
  member: PointsMember | null;
  onClose: () => void;
  onEdit: (member: PointsMember) => void;
  onAward: (member: PointsMember) => void;
}) {
  const client = useQueryClient();
  const key = member ? memberKey(member) : '';
  const history = useQuery({
    queryKey: ['points', prefix, 'history', key],
    queryFn: () => api<PointsHistory>(`/api/points/${prefix}/users/${encodeURIComponent(key)}/points`),
    enabled: Boolean(key),
    refetchInterval: POINTS_REFETCH_MS,
  });
  const remove = useMutation({
    mutationFn: (id: number) => send(`/api/points/${prefix}/entries/${id}`, 'DELETE'),
    onSuccess: () => refreshPoints(client, prefix),
  });
  const entries = history.data?.points_history ?? [];
  const groups = useMemo(() => groupEntries(entries), [entries]);
  const recent = useMemo(() => givenSince(entries, Date.now() - 30 * DAY_MS), [entries]);
  return (
    <Drawer
      open={Boolean(member)}
      onClose={onClose}
      title={member?.name ?? member?.email ?? 'Member'}
      description={member?.email ?? member?.username ?? undefined}
    >
      {member ? (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={member.discord_linked ? 'ok' : 'muted'}>{member.discord_linked ? 'Discord linked' : 'Discord not linked'}</Badge>
            {member.major ? <span className="text-xs text-muted">{member.major}</span> : null}
            {member.academic_standing ? <span className="text-xs text-muted">{member.academic_standing}</span> : null}
            {member.asu_id ? <span className="text-xs text-muted">Student ID {member.asu_id}</span> : null}
          </div>
          <dl className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-line p-3">
              <dt className="text-xs text-muted">Total</dt>
              <dd className={cx('mt-1 text-2xl font-semibold tabular-nums', member.points < 0 && 'text-bad')} aria-label="Total points">
                {compact(member.points)}
              </dd>
            </div>
            <div className="rounded-lg border border-line p-3">
              <dt className="text-xs text-muted">Last 30 days</dt>
              <dd className="mt-1 text-2xl font-semibold tabular-nums">{history.data ? `+${compact(recent)}` : '-'}</dd>
            </div>
          </dl>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" onClick={() => onAward(member)}>
              <Plus className="size-4" /> Award points
            </Button>
            <Button onClick={() => onEdit(member)}>
              <Pencil className="size-4" /> Edit details
            </Button>
          </div>
          <section aria-label="Points by event">
            <h3 className="mb-2 text-sm font-medium">
              By event{history.data ? <span className="ml-1.5 font-normal text-muted">{entryCount(entries.length)}</span> : null}
            </h3>
            {history.error ? <ErrorNote error={history.error} /> : null}
            {remove.error ? (
              <div className="mb-3">
                <ErrorNote error={remove.error} />
              </div>
            ) : null}
            {history.isLoading ? (
              <SkeletonRows rows={4} />
            ) : groups.length ? (
              <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line">
                {groups.map((g) => (
                  <EventGroupRow key={g.key} group={g} busy={remove.isPending} onDelete={(id) => remove.mutate(id)} />
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">No points yet.</p>
            )}
          </section>
        </div>
      ) : null}
    </Drawer>
  );
}

// One event or store order: its total, then each entry. Store entries are the order's hold and refund, which the
// Store page changes, so they have no delete.
function EventGroupRow({ group, busy, onDelete }: { group: EntryGroup; busy: boolean; onDelete: (id: number) => void }) {
  // An order holds its points until a cancel or a delete gives them back
  const state = group.order === null ? null : group.total < 0 ? 'held' : 'refunded';
  return (
    <li className="px-3 py-2.5">
      <div className="flex items-baseline gap-2">
        <span className="min-w-0 flex-1 truncate text-sm font-medium">{group.label}</span>
        {state ? <span className="text-xs text-muted">{state}</span> : null}
        <span className={cx('text-sm font-medium tabular-nums', group.total < 0 && 'text-bad')}>{signed(group.total)}</span>
      </div>
      <ul className="mt-1 space-y-0.5">
        {group.entries.map((e) => (
          <li key={e.id} className="flex items-center gap-2 text-xs text-muted">
            <span className="min-w-0 flex-1 truncate">
              {group.order !== null ? (e.points < 0 ? 'Purchase' : 'Refund') : (e.awarded_by_officer ?? 'Unknown')}, {timeAgo(e.timestamp)}
            </span>
            {group.entries.length > 1 ? <span className="tabular-nums">{signed(e.points)}</span> : null}
            {group.order === null ? (
              <DeleteButton
                title="Delete entry"
                label={e.event ? `Delete the entry for ${e.event}` : 'Delete the entry with no event'}
                question={e.event ? `Delete ${signed(e.points)} points for ${e.event}?` : `Delete ${signed(e.points)} points?`}
                onDelete={() => onDelete(e.id)}
                disabled={busy}
              />
            ) : (
              <span className="w-8 shrink-0" aria-hidden />
            )}
          </li>
        ))}
      </ul>
    </li>
  );
}
