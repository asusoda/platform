import { CalendarCheck, Coins, Plus, RefreshCw, Upload, UserPlus, Users } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';
import { TabBar, useTabParam } from '../../components/tabs';
import { Button, Notice, PageHeader, Stat, StatGrid } from '../../components/ui';
import { compact } from '../../lib/format';
import { useCurrentOrg } from '../../lib/org';
import type { PointsMember } from '../../lib/types';
import { AwardDialog } from './award';
import { DiscordSyncDialog } from './discord-sync';
import { EventsTab } from './events';
import { MemberDrawer } from './member-drawer';
import { MemberDialog } from './member-form';
import { MembersTab } from './members';
import { entryCount, type EventGroup, givenSince, importRunning, memberKey, pointsImportsQuery, usePoints } from './shared';
import { ImportProgress, UploadDialog } from './upload';

const TABS = [
  { id: 'members', label: 'Members' },
  { id: 'events', label: 'Events' },
] as const;

export function PointsPage() {
  const { prefix } = useCurrentOrg();
  const [tab, setTab] = useTabParam(TABS);
  const [awarding, setAwarding] = useState<{ member: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [editing, setEditing] = useState<{ member: PointsMember | null } | null>(null);
  const [hiddenImport, setHiddenImport] = useState<number | null>(null);
  const { members, entries } = usePoints(prefix);
  const imports = useQuery(pointsImportsQuery(prefix));
  const list = members.data?.users ?? [];
  // The open member is in the URL (?member=<email or uuid>), so a link opens the drawer.
  const [params, setParams] = useSearchParams();
  const openKey = params.get('member');
  const viewing = openKey ? (list.find((m) => memberKey(m) === openKey || m.uuid === openKey) ?? null) : null;
  const setViewing = (m: PointsMember | null) =>
    setParams(
      (p) => {
        const next = new URLSearchParams(p);
        if (m) next.set('member', memberKey(m));
        else next.delete('member');
        return next;
      },
      { replace: true },
    );
  const lastImport = imports.data?.imports[0];
  const showImport = lastImport && importRunning(lastImport) && lastImport.id !== hiddenImport ? lastImport : null;

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
  const given = givenSince(entries.data ?? [], since);

  return (
    <>
      <PageHeader
        action={
          <>
            <Button onClick={() => setSyncing(true)} aria-label="Add from Discord">
              <RefreshCw className="size-4" /> <span className="hidden sm:inline">Add from Discord</span>
            </Button>
            <Button onClick={() => setEditing({ member: null })} aria-label="Add member">
              <UserPlus className="size-4" /> <span className="hidden sm:inline">Add member</span>
            </Button>
            <Button onClick={() => setUploading(true)} aria-label="Upload CSV">
              <Upload className="size-4" /> <span className="hidden sm:inline">Upload CSV</span>
            </Button>
            <Button variant="primary" onClick={() => setAwarding({ member: '' })}>
              <Plus className="size-4" /> Award points
            </Button>
          </>
        }
      />
      {showImport ? (
        <Notice onDismiss={() => setHiddenImport(showImport.id)}>
          <div className="mb-2">CSV import for {showImport.event} is running.</div>
          <ImportProgress done={showImport.rows_done} total={showImport.rows_total} />
        </Notice>
      ) : null}
      <StatGrid className="mb-6">
        <Stat label="Members" value={members.data ? compact(members.data.total_users) : '-'} icon={<Users className="size-4" />} />
        <Stat
          label="Total points"
          value={members.data ? compact(list.reduce((n, m) => n + m.points, 0)) : '-'}
          icon={<Coins className="size-4" />}
        />
        <Stat
          label="Given in 30 days"
          value={entries.data ? compact(given) : '-'}
          sub={entries.data ? entryCount(recent.length) : undefined}
        />
        <Stat label="Events" value={entries.data ? groups.length : '-'} icon={<CalendarCheck className="size-4" />} />
      </StatGrid>
      <TabBar label="Points" tabs={TABS} value={tab} onChange={setTab} />
      {tab === 'events' ? (
        <EventsTab prefix={prefix} groups={groups} members={list} loading={entries.isLoading} error={entries.error} />
      ) : (
        <MembersTab members={members} onOpen={setViewing} />
      )}
      <AwardDialog prefix={prefix} members={list} open={Boolean(awarding)} member={awarding?.member} onClose={() => setAwarding(null)} />
      <UploadDialog prefix={prefix} open={uploading} onClose={() => setUploading(false)} />
      <DiscordSyncDialog prefix={prefix} open={syncing} onClose={() => setSyncing(false)} />
      <MemberDrawer
        prefix={prefix}
        member={viewing}
        onClose={() => setViewing(null)}
        onEdit={(m) => setEditing({ member: m })}
        onAward={(m) => setAwarding({ member: memberKey(m) })}
      />
      <MemberDialog prefix={prefix} member={editing?.member ?? null} open={Boolean(editing)} onClose={() => setEditing(null)} />
    </>
  );
}
