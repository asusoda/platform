import { CalendarCheck, Coins, Plus, Upload, Users } from 'lucide-react';
import { useMemo, useState } from 'react';
import { TabBar, useTabParam } from '../../components/tabs';
import { Button, PageHeader, Stat, StatGrid } from '../../components/ui';
import { compact } from '../../lib/format';
import { useCurrentOrg } from '../../lib/org';
import type { PointsMember } from '../../lib/types';
import { AwardDialog } from './award';
import { EventsTab } from './events';
import { HistoryDialog } from './history';
import { MembersTab } from './members';
import { entryCount, type EventGroup, usePoints } from './shared';
import { UploadDialog } from './upload';

const TABS = [
  { id: 'members', label: 'Members' },
  { id: 'events', label: 'Events' },
] as const;

export function PointsPage() {
  const { prefix } = useCurrentOrg();
  const [tab, setTab] = useTabParam(TABS);
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
        description="Members and their points, and the events that gave points."
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
      <StatGrid className="mb-6">
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
      </StatGrid>
      <TabBar label="Points" tabs={TABS} value={tab} onChange={setTab} />
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
