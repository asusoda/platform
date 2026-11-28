import { useQuery } from '@tanstack/react-query';
import { Bot, Building2, CircleCheck, Cpu, Gauge, HardDrive, ListTodo, MemoryStick, Users, UserX } from 'lucide-react';
import { Link } from 'react-router';
import { ActivityList } from '../../components/activity-list';
import { OrgMark } from '../../components/org-mark';
import { Badge, Card, CardHeader, EmptyState, ErrorNote, PageHeader, quietLink, Row, SkeletonRows, Stat, StatGrid } from '../../components/ui';
import { api } from '../../lib/api';
import { bytes } from '../../lib/format';
import type { AuditEntry, SuperadminOrg } from '../../lib/types';
import { BotBadge, Fact, queueText, used, useServerHealth } from './server';
import { useAdminOrgs } from './shared';

const RECENT = 8;

// What an org needs from the superadmin: an officer role, room under a limit, a look at its errors.
function issues(o: SuperadminOrg): string[] {
  const out: string[] = [];
  if (o.is_active && !o.officer_role_id) out.push('No officer role');
  if (o.near.length) out.push(o.near.length === 1 ? 'Near a limit' : `Near ${o.near.length} limits`);
  if (o.open_errors) out.push(o.open_errors === 1 ? '1 open error' : `${o.open_errors} open errors`);
  return out;
}

function ServerSummary() {
  const server = useServerHealth();
  const s = server.data;
  const memoryUsed = s?.memory ? s.memory.total - s.memory.available : null;
  return (
    <Card>
      <CardHeader
        title="Server"
        action={
          <Link to="/admin/server" className={quietLink}>
            Details
          </Link>
        }
      />
      {server.error ? (
        <div className="p-4">
          <ErrorNote error={server.error} />
        </div>
      ) : null}
      {server.isLoading ? <SkeletonRows rows={4} /> : null}
      {s ? (
        <dl className="space-y-3 p-4 text-sm">
          <Fact label="Load" icon={Cpu}>
            {s.load ? s.load[0].toFixed(2) : '-'}
            {s.cpus ? ` on ${s.cpus} CPUs` : ''}
          </Fact>
          <Fact label="Memory" icon={MemoryStick}>
            {used(memoryUsed, s.memory?.total)}
            {s.memory ? ` of ${bytes(s.memory.total)}` : ''}
          </Fact>
          <Fact label="Disk" icon={HardDrive}>
            {used(s.disk?.used, s.disk?.total)}
            {s.disk ? ` of ${bytes(s.disk.total)}` : ''}
          </Fact>
          <Fact label="Discord bot" icon={Bot}>
            <BotBadge ready={s.bot_ready} />
          </Fact>
          <Fact label="Jobs" icon={ListTodo}>
            {queueText(s)}
          </Fact>
        </dl>
      ) : null}
    </Card>
  );
}

function Attention({ orgs }: { orgs: SuperadminOrg[] }) {
  const flagged = orgs.map((o) => ({ org: o, issues: issues(o) })).filter((x) => x.issues.length);
  return (
    <Card>
      <CardHeader
        title="Needs a look"
        action={
          <Link to="/admin/orgs" className={quietLink}>
            Organizations
          </Link>
        }
      />
      {flagged.length ? (
        flagged.map(({ org, issues }) => (
          <Row key={org.id}>
            <OrgMark name={org.name} logoUrl={org.icon_url} className="size-6" />
            <span className="min-w-0 flex-1 truncate text-sm font-medium">{org.name}</span>
            <span className="flex flex-wrap justify-end gap-1.5">
              {issues.map((i) => (
                <Badge key={i} tone="warn">
                  {i}
                </Badge>
              ))}
            </span>
          </Row>
        ))
      ) : (
        <EmptyState icon={CircleCheck} title="Nothing needs a look" />
      )}
    </Card>
  );
}

function RecentActivity() {
  const log = useQuery({
    queryKey: ['superadmin-audit-recent'],
    queryFn: () => api<{ entries: AuditEntry[] }>(`/api/superadmin/audit?limit=${RECENT}`).then((b) => b.entries),
  });
  return (
    <Card>
      <CardHeader
        title="Recent activity"
        action={
          <Link to="/admin/audit" className={quietLink}>
            Audit log
          </Link>
        }
      />
      {log.error ? (
        <div className="p-4">
          <ErrorNote error={log.error} />
        </div>
      ) : log.isLoading ? (
        <SkeletonRows rows={4} />
      ) : (
        <ActivityList entries={log.data ?? []} empty="Nothing recorded yet." showOrg />
      )}
    </Card>
  );
}

// The superadmin home: the orgs in numbers, the server, the orgs that need something, and the latest changes.
export function OverviewPage() {
  const orgs = useAdminOrgs();
  const list = orgs.data ?? [];
  const active = list.filter((o) => o.is_active);
  return (
    <>
      <PageHeader />
      {orgs.error ? (
        <div className="mb-6">
          <ErrorNote error={orgs.error} />
        </div>
      ) : null}
      <StatGrid className="mb-6">
        <Stat label="Organizations" value={orgs.data ? list.length : '-'} sub={orgs.data ? `${active.length} active` : undefined} icon={<Building2 className="size-4" />} />
        <Stat label="Members" value={orgs.data ? list.reduce((n, o) => n + o.members, 0).toLocaleString() : '-'} icon={<Users className="size-4" />} />
        <Stat label="No officer role" value={orgs.data ? active.filter((o) => !o.officer_role_id).length : '-'} icon={<UserX className="size-4" />} />
        <Stat label="Near a limit" value={orgs.data ? list.filter((o) => o.near.length).length : '-'} icon={<Gauge className="size-4" />} />
      </StatGrid>
      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ServerSummary />
        {orgs.isLoading ? (
          <Card>
            <SkeletonRows rows={4} />
          </Card>
        ) : (
          <Attention orgs={list} />
        )}
      </div>
      <RecentActivity />
    </>
  );
}
