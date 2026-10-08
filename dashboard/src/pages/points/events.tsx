import { useMutation, useQueryClient } from '@tanstack/react-query';
import { CalendarCheck } from 'lucide-react';
import { useMemo } from 'react';
import { Card, CardHeader, cx, DeleteButton, EmptyState, ErrorNote, SkeletonRows, Table, Td, Th, Tr } from '../../components/ui';
import { send } from '../../lib/api';
import { compact, timeAgo } from '../../lib/format';
import type { PointsMember } from '../../lib/types';
import { entryCount, type EventGroup } from './shared';

export function EventsTab({ prefix, groups, members, loading, error }: {
  prefix: string;
  groups: EventGroup[];
  members: PointsMember[];
  loading: boolean;
  error: unknown;
}) {
  const client = useQueryClient();
  const emails = useMemo(() => new Map(members.map((m) => [m.id, m.email])), [members]);
  // The route deletes one entry for each call: the first entry of that member for that event.
  const remove = useMutation({
    mutationFn: async (group: EventGroup) => {
      for (const entry of group.entries) {
        const email = emails.get(entry.user_id);
        if (email) await send(`/api/points/${prefix}/delete_points`, 'DELETE', { user_email: email, event: group.event });
      }
    },
    onSettled: () => client.invalidateQueries({ queryKey: ['points', prefix] }),
  });
  return (
    <Card>
      <CardHeader title="Events" hint="Point entries grouped by event name, newest first." />
      {remove.error ? (
        <div className="border-b border-line p-4">
          <ErrorNote error={remove.error} />
        </div>
      ) : null}
      {error ? (
        <div className="p-4">
          <ErrorNote error={error} />
        </div>
      ) : loading ? (
        <SkeletonRows rows={5} />
      ) : groups.length ? (
        <Table>
          <thead>
            <tr>
              <Th>Event</Th>
              <Th className="hidden text-right sm:table-cell">Entries</Th>
              <Th className="text-right">Points</Th>
              <Th className="hidden text-right sm:table-cell">Last entry</Th>
              <Th>
                <span className="sr-only">Actions</span>
              </Th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => {
              const deletable = g.entries.filter((e) => emails.get(e.user_id)).length;
              const skipped = g.entries.length - deletable;
              const note = skipped ? ` ${entryCount(skipped)} of people who are not members stay.` : '';
              const effect = g.total < 0 ? 'Members get these points back.' : 'Members lose these points.';
              return (
                <Tr key={g.event}>
                  <Td className="w-full max-w-0">
                    <div className="truncate font-medium">{g.event}</div>
                    <div className="truncate text-xs text-muted sm:hidden">
                      {entryCount(g.entries.length)}, {timeAgo(g.last)}
                    </div>
                  </Td>
                  <Td className="hidden text-right text-muted tabular-nums sm:table-cell">{g.entries.length}</Td>
                  <Td className={cx('text-right tabular-nums', g.total < 0 && 'text-bad')}>{compact(g.total)}</Td>
                  <Td className="hidden text-right text-xs whitespace-nowrap text-muted sm:table-cell">{timeAgo(g.last)}</Td>
                  <Td className="pr-2 pl-0">
                    <DeleteButton
                      title="Delete the entries of this event"
                      label={`Delete the entries of ${g.event}`}
                      question={`Delete ${entryCount(deletable)} of ${g.event}? ${effect}${note}`}
                      onDelete={() => remove.mutate(g)}
                      disabled={!deletable || remove.isPending}
                    />
                  </Td>
                </Tr>
              );
            })}
          </tbody>
        </Table>
      ) : (
        <EmptyState icon={CalendarCheck} title="No events yet">
          Award points with an event name, or upload event check-ins.
        </EmptyState>
      )}
    </Card>
  );
}
