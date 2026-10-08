import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarCheck, Coins, Plus, Search, Trash2, Upload, Users } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';
import { ModuleGate } from '../components/module-gate';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  cx,
  Dialog,
  EmptyState,
  ErrorNote,
  Field,
  FormActions,
  Input,
  PageHeader,
  SkeletonRows,
  Stat,
  Table,
  Td,
  Th,
  Tr,
} from '../components/ui';
import { api, send } from '../lib/api';
import { compact, timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import type { PointEntry, PointsHistory, PointsMember } from '../lib/types';

const TABS = [
  { id: 'members', label: 'Members' },
  { id: 'events', label: 'Events' },
] as const;

type EventGroup = { event: string; entries: PointEntry[]; total: number; last: string | null };

// A Discord user ID: the add_points route finds members by it.
const DISCORD_ID = /^[0-9]{15,25}$/;

const entryCount = (n: number) => (n === 1 ? '1 entry' : `${n} entries`);
const signed = (n: number) => `${n > 0 ? '+' : ''}${Number.isInteger(n) ? n : n.toFixed(1)}`;
const memberKey = (m: { email: string | null; uuid?: string }) => m.email ?? m.uuid ?? '';

function usePoints(prefix: string) {
  const members = useQuery({
    queryKey: ['points', prefix, 'members'],
    queryFn: () => api<{ total_users: number; users: PointsMember[] }>(`/api/points/${prefix}/users`),
  });
  const entries = useQuery({
    queryKey: ['points', prefix, 'entries'],
    queryFn: () => api<PointEntry[]>(`/api/points/${prefix}/get_points`),
  });
  return { members, entries };
}

function AwardDialog({
  prefix,
  members,
  open,
  onClose,
}: {
  prefix: string;
  members: PointsMember[];
  open: boolean;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const [draft, setDraft] = useState({ member: '', points: '', event: '', by: '' });
  const award = useMutation({
    mutationFn: () => {
      const body = { points: Number(draft.points), event: draft.event || null, awarded_by_officer: draft.by || null };
      return DISCORD_ID.test(draft.member)
        ? send(`/api/points/${prefix}/add_points`, 'POST', { ...body, user_discord_id: draft.member })
        : send(`/api/points/${prefix}/assign_points`, 'POST', { ...body, user_identifier: draft.member });
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['points', prefix] });
      setDraft({ member: '', points: '', event: '', by: '' });
      onClose();
    },
  });
  const set = (k: keyof typeof draft) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  const points = Number(draft.points);
  return (
    <Dialog open={open} onClose={onClose} title="Award points" description="Add points to one member. Use a negative number to take points away.">
      <form
        className="space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          award.mutate();
        }}
      >
        <Field label="Member" hint="Email, username or Discord user ID.">
          <Input value={draft.member} onChange={set('member')} list="points-members" placeholder="ada@example.edu" required autoFocus />
        </Field>
        <datalist id="points-members">
          {members.map((m) => (m.email ? <option key={m.id} value={m.email}>{m.name}</option> : null))}
        </datalist>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Points">
            <Input type="number" step="any" value={draft.points} onChange={set('points')} placeholder="10" required />
          </Field>
          <Field label="Event" hint="Optional. Groups the entry on the Events tab.">
            <Input value={draft.event} onChange={set('event')} placeholder="Build night" />
          </Field>
        </div>
        <Field label="Awarded by" hint="Optional. Empty records your name.">
          <Input value={draft.by} onChange={set('by')} />
        </Field>
        <FormActions error={award.error}>
          <Button variant="primary" disabled={!draft.member || !points || award.isPending}>
            Award points
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </FormActions>
      </form>
    </Dialog>
  );
}

function UploadDialog({ prefix, open, onClose }: { prefix: string; open: boolean; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [event, setEvent] = useState('');
  const [points, setPoints] = useState('');
  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append('file', file as File);
      form.append('event_name', event);
      form.append('event_points', points);
      return api<{ message: string }>(`/api/points/${prefix}/uploadEventCSV`, { method: 'POST', body: form });
    },
  });
  const close = () => {
    upload.reset();
    setFile(null);
    setEvent('');
    setPoints('');
    onClose();
  };
  return (
    <Dialog
      open={open}
      onClose={close}
      title="Upload event check-ins"
      description="Gives the points to each row with a check-in date, one time for each email. A member that is not found is added."
    >
      {upload.isSuccess ? (
        <div className="space-y-4">
          <p role="status" className="rounded-md border border-ok/30 bg-ok/10 px-3 py-2 text-sm text-ok">
            The server adds the points in the background. Reload this page in a minute to see them.
          </p>
          <Button onClick={close}>Close</Button>
        </div>
      ) : (
        <form
          className="space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            upload.mutate();
          }}
        >
          <Field label="CSV file" hint="Columns: Email, First Name, Last Name and Checked-In Date.">
            <Input
              type="file"
              accept=".csv,text/csv"
              required
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="h-auto py-1.5 file:mr-3 file:cursor-pointer file:rounded file:border-0 file:bg-panel-2 file:px-2 file:py-1 file:text-sm"
            />
          </Field>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Event">
              <Input value={event} onChange={(e) => setEvent(e.target.value)} placeholder="Build night" required />
            </Field>
            <Field label="Points for each member" hint="A whole number.">
              <Input type="number" step={1} value={points} onChange={(e) => setPoints(e.target.value)} placeholder="10" required />
            </Field>
          </div>
          <FormActions error={upload.error}>
            <Button variant="primary" disabled={!file || !event || !points || upload.isPending}>
              <Upload className="size-4" /> Upload
            </Button>
            <Button type="button" variant="ghost" onClick={close}>
              Cancel
            </Button>
          </FormActions>
        </form>
      )}
    </Dialog>
  );
}

function HistoryDialog({ prefix, member, onClose }: { prefix: string; member: PointsMember | null; onClose: () => void }) {
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
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Delete entry"
                      aria-label={`Delete the entry for ${e.event}`}
                      className="hover:text-bad"
                      disabled={remove.isPending}
                      onClick={() => {
                        if (confirm(`Delete ${signed(e.points)} points for ${e.event}?`)) remove.mutate(e.event as string);
                      }}
                    >
                      <Trash2 className="size-4" />
                    </Button>
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

function MembersTab({ members, onOpen }: { members: ReturnType<typeof usePoints>['members']; onOpen: (m: PointsMember) => void }) {
  const [query, setQuery] = useState('');
  const ranked = useMemo(
    () => [...(members.data?.users ?? [])].sort((a, b) => b.points - a.points || (a.name ?? '').localeCompare(b.name ?? '')),
    [members.data],
  );
  const q = query.trim().toLowerCase();
  const shown = q
    ? ranked.filter((m) => [m.name, m.email, m.username].some((v) => v?.toLowerCase().includes(q)))
    : ranked;
  return (
    <Card>
      <CardHeader
        title="Leaderboard"
        hint="Members by points. Store orders take points away. Select a member to see each entry."
      />
      <div className="border-b border-line p-3">
        <label className="relative block">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find a member" aria-label="Find a member" className="pl-9" />
        </label>
      </div>
      {members.error ? (
        <div className="p-4">
          <ErrorNote error={members.error} />
        </div>
      ) : members.isLoading ? (
        <SkeletonRows rows={6} />
      ) : shown.length ? (
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
            {shown.map((m) => (
              <Tr key={m.id}>
                <Td className="pr-0 text-xs text-muted tabular-nums">{ranked.indexOf(m) + 1}</Td>
                <Td className="w-full max-w-0">
                  <button type="button" className="block w-full min-w-0 cursor-pointer text-left" onClick={() => onOpen(m)}>
                    <span className="block truncate font-medium hover:underline">{m.name ?? m.username ?? 'No name'}</span>
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
      ) : (
        <EmptyState icon={Users} title={q ? 'No member matches' : 'No members yet'}>
          {q ? 'Try a name, email or username.' : 'Members join through the Discord server, the store or a check-in upload.'}
        </EmptyState>
      )}
    </Card>
  );
}

function EventsTab({ prefix, groups, members, loading, error }: {
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
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Delete the entries of this event"
                      aria-label={`Delete the entries of ${g.event}`}
                      className="hover:text-bad"
                      disabled={!deletable || remove.isPending}
                      onClick={() => {
                        const skipped = g.entries.length - deletable;
                        const note = skipped ? ` ${entryCount(skipped)} of people who are not members stay.` : '';
                        const effect = g.total < 0 ? 'Members get these points back.' : 'Members lose these points.';
                        if (confirm(`Delete ${entryCount(deletable)} of ${g.event}? ${effect}${note}`)) remove.mutate(g);
                      }}
                    >
                      <Trash2 className="size-4" />
                    </Button>
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

function Points() {
  const { prefix } = useCurrentOrg();
  const [params, setParams] = useSearchParams();
  const tab = TABS.find((t) => t.id === params.get('tab'))?.id ?? 'members';
  const [awarding, setAwarding] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [viewing, setViewing] = useState<PointsMember | null>(null);
  const { members, entries } = usePoints(prefix);
  const list = members.data?.users ?? [];

  const groups = useMemo(() => {
    const byEvent = new Map<string, EventGroup>();
    for (const e of entries.data ?? []) {
      if (!e.event) continue;
      const g = byEvent.get(e.event) ?? { event: e.event, entries: [], total: 0, last: null };
      g.entries.push(e);
      g.total += e.points;
      if (e.timestamp && (!g.last || e.timestamp > g.last)) g.last = e.timestamp;
      byEvent.set(e.event, g);
    }
    return [...byEvent.values()].sort((a, b) => (b.last ?? '').localeCompare(a.last ?? ''));
  }, [entries.data]);

  const since = Date.now() - 30 * 86_400_000;
  const recent = (entries.data ?? []).filter((e) => e.points > 0 && e.timestamp && new Date(e.timestamp).getTime() >= since);

  return (
    <>
      <PageHeader
        title="Points"
        description="Members and their points, the events that gave points, and event check-in uploads."
        action={
          <>
            <Button onClick={() => setUploading(true)}>
              <Upload className="size-4" /> Upload CSV
            </Button>
            <Button variant="primary" onClick={() => setAwarding(true)}>
              <Plus className="size-4" /> Award points
            </Button>
          </>
        }
      />
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Members" value={members.data ? compact(members.data.total_users) : '-'} icon={<Users className="size-4" />} />
        <Stat
          label="Points held"
          value={members.data ? compact(list.reduce((n, m) => n + m.points, 0)) : '-'}
          icon={<Coins className="size-4" />}
        />
        <Stat
          label="Given in 30 days"
          value={entries.data ? compact(recent.reduce((n, e) => n + e.points, 0)) : '-'}
          sub={entries.data ? entryCount(recent.length) : undefined}
        />
        <Stat label="Events" value={entries.data ? groups.length : '-'} icon={<CalendarCheck className="size-4" />} />
      </div>
      <div role="tablist" aria-label="Points" className="mb-6 flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setParams(t.id === 'members' ? {} : { tab: t.id }, { replace: true })}
            className={cx(
              '-mb-px h-9 cursor-pointer border-b-2 px-3 text-sm transition-colors',
              tab === t.id ? 'border-fg font-medium text-fg' : 'border-transparent text-muted hover:text-fg',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'events' ? (
        <EventsTab prefix={prefix} groups={groups} members={list} loading={entries.isLoading} error={entries.error} />
      ) : (
        <MembersTab members={members} onOpen={setViewing} />
      )}
      <AwardDialog prefix={prefix} members={list} open={awarding} onClose={() => setAwarding(false)} />
      <UploadDialog prefix={prefix} open={uploading} onClose={() => setUploading(false)} />
      <HistoryDialog prefix={prefix} member={viewing} onClose={() => setViewing(null)} />
    </>
  );
}

export function PointsPage() {
  return (
    <ModuleGate module="points" title="Points">
      <Points />
    </ModuleGate>
  );
}
