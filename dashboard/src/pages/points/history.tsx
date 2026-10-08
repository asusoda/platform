import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { cx, DeleteButton, Dialog, ErrorNote, SkeletonRows, Table, Td, Th, Tr } from '../../components/ui';
import { api, send } from '../../lib/api';
import { compact, timeAgo } from '../../lib/format';
import type { PointsHistory, PointsMember } from '../../lib/types';
import { entryCount, memberKey, signed } from './shared';

export function HistoryDialog({ prefix, member, onClose }: { prefix: string; member: PointsMember | null; onClose: () => void }) {
  const client = useQueryClient();
  const key = member ? memberKey(member) : '';
  const history = useQuery({
    queryKey: ['points', prefix, 'history', key],
    queryFn: () => api<PointsHistory>(`/api/points/${prefix}/users/${encodeURIComponent(key)}/points`),
    enabled: Boolean(key),
  });
  const remove = useMutation({
    mutationFn: (event: string) => send(`/api/points/${prefix}/delete_points`, 'DELETE', { user_email: member?.email, event }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['points', prefix] }),
  });
  const entries = history.data?.points_history ?? [];
  return (
    <Dialog
      open={Boolean(member)}
      onClose={onClose}
      title={member?.name ?? member?.email ?? 'Member'}
      description={history.data ? `${compact(history.data.total_points)} points, ${entryCount(entries.length)}` : member?.email}
      wide
    >
      {history.error ? <ErrorNote error={history.error} /> : null}
      {remove.error ? (
        <div className="mb-3">
          <ErrorNote error={remove.error} />
        </div>
      ) : null}
      {history.isLoading ? (
        <SkeletonRows rows={4} />
      ) : entries.length ? (
        <Table>
          <thead>
            <tr>
              <Th>Event</Th>
              <Th className="text-right">Points</Th>
              <Th className="hidden sm:table-cell">By</Th>
              <Th className="hidden text-right sm:table-cell">When</Th>
              <Th>
                <span className="sr-only">Actions</span>
              </Th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <Tr key={e.id}>
                <Td className="w-full max-w-0">
                  <div className="truncate">{e.event ?? <span className="text-muted">No event</span>}</div>
                  <div className="truncate text-xs text-muted sm:hidden">{timeAgo(e.timestamp)}</div>
                </Td>
                <Td className={cx('text-right tabular-nums', e.points < 0 && 'text-bad')}>{signed(e.points)}</Td>
                <Td className="hidden max-w-40 truncate text-xs text-muted sm:table-cell">{e.awarded_by_officer ?? ''}</Td>
                <Td className="hidden text-right text-xs whitespace-nowrap text-muted sm:table-cell">{timeAgo(e.timestamp)}</Td>
                <Td className="pr-2 pl-0">
                  {member?.email && e.event ? (
                    <DeleteButton
                      title="Delete entry"
                      label={`Delete the entry for ${e.event}`}
                      question={`Delete ${signed(e.points)} points for ${e.event}?`}
                      onDelete={() => remove.mutate(e.event as string)}
                      disabled={remove.isPending}
                    />
                  ) : null}
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      ) : (
        <p className="text-sm text-muted">No points yet.</p>
      )}
    </Dialog>
  );
}
