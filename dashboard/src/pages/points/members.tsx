import { Users } from 'lucide-react';
import { useDeferredValue, useMemo, useState } from 'react';
import {
  Badge,
  Card,
  CardHeader,
  cx,
  EmptyState,
  ErrorNote,
  SearchInput,
  ShowMore,
  SkeletonRows,
  Table,
  Td,
  Th,
  Tr,
  useShowMore,
} from '../../components/ui';
import { compact, timeAgo } from '../../lib/format';
import type { PointsMember } from '../../lib/types';
import type { usePoints } from './shared';

export function MembersTab({ members, onOpen }: { members: ReturnType<typeof usePoints>['members']; onOpen: (m: PointsMember) => void }) {
  const [query, setQuery] = useState('');
  const q = useDeferredValue(query.trim().toLowerCase());
  // Members by points, each with its rank, and the lowercase text a search looks in.
  const ranked = useMemo(
    () =>
      [...(members.data?.users ?? [])]
        .sort((a, b) => b.points - a.points || (a.name ?? '').localeCompare(b.name ?? ''))
        .map((m, i) => ({ m, rank: i + 1, text: [m.name, m.email, m.username].filter(Boolean).join(' ').toLowerCase() })),
    [members.data],
  );
  const shown = useMemo(() => (q ? ranked.filter((r) => r.text.includes(q)) : ranked), [ranked, q]);
  const page = useShowMore(shown, q);
  return (
    <Card>
      <CardHeader
        title="Leaderboard"
        hint="Members by points. Store orders take points away. Select a member to see each entry."
      />
      <div className="border-b border-line p-3">
        <SearchInput value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find a member" aria-label="Find a member" />
      </div>
      {members.error ? (
        <div className="p-4">
          <ErrorNote error={members.error} />
        </div>
      ) : members.isLoading ? (
        <SkeletonRows rows={6} />
      ) : shown.length ? (
        <>
          <Table>
            <thead>
              <tr>
                <Th className="w-12 pr-0">#</Th>
                <Th>Member</Th>
                <Th className="text-right">Points</Th>
                <Th className="hidden md:table-cell">Discord</Th>
                <Th className="hidden text-right sm:table-cell">Joined</Th>
              </tr>
            </thead>
            <tbody>
              {page.shown.map(({ m, rank }) => (
                <Tr key={m.id}>
                  <Td className="pr-0 text-xs text-muted tabular-nums">{rank}</Td>
                  <Td className="w-full max-w-0">
                    <button type="button" className="group block w-full min-w-0 cursor-pointer rounded-sm text-left" onClick={() => onOpen(m)}>
                      <span className="block truncate font-medium group-hover:underline">{m.name ?? m.username ?? 'No name'}</span>
                      <span className="block truncate text-xs text-muted">{m.email ?? m.username ?? m.uuid}</span>
                    </button>
                  </Td>
                  <Td className={cx('text-right font-medium tabular-nums', m.points < 0 && 'text-bad')}>{compact(m.points)}</Td>
                  <Td className="hidden md:table-cell">
                    <Badge tone={m.discord_linked ? 'ok' : 'muted'}>{m.discord_linked ? 'linked' : 'not linked'}</Badge>
                  </Td>
                  <Td className="hidden text-right text-xs whitespace-nowrap text-muted sm:table-cell">{timeAgo(m.joined_at)}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
          <ShowMore list={page} noun="members" />
        </>
      ) : (
        <EmptyState icon={Users} title={q ? 'No member matches' : 'No members yet'}>
          {q ? 'Try a name, email or username.' : 'Members join through the Discord server, the store or a check-in upload.'}
        </EmptyState>
      )}
    </Card>
  );
}
