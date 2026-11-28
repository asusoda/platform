import { useQuery } from '@tanstack/react-query';
import { Activity, Bot, Clock, Cpu, Database, HardDrive, ListTodo, MemoryStick } from 'lucide-react';
import type { ComponentType, ReactNode } from 'react';
import { Badge, Card, CardHeader, ErrorNote, PageHeader, PageSkeleton, Stat, StatGrid } from '../../components/ui';
import { api } from '../../lib/api';
import { bytes, elapsed } from '../../lib/format';
import type { ServerHealth } from '../../lib/types';

export const used = (part: number | null | undefined, total: number | null | undefined) =>
  part != null && total ? `${Math.round((part / total) * 100)}%` : '-';

// The server's health, every 30 seconds. Overview and Server share it.
export function useServerHealth() {
  return useQuery({
    queryKey: ['superadmin-server'],
    queryFn: () => api<ServerHealth>('/api/superadmin/server'),
    refetchInterval: 30_000,
  });
}

// The jobs line: the count of each status, or the backend when the queue is in each process.
export const queueText = (s: ServerHealth) =>
  s.jobs.queue
    ? Object.entries(s.jobs.queue)
        .map(([status, n]) => `${n} ${status}`)
        .join(', ') || 'Queue empty'
    : `${s.jobs.backend}, in each process`;

// One line of a facts list: an icon and label on the left, the value on the right.
export function Fact({ label, icon: Icon, children }: { label: string; icon: ComponentType<{ className?: string }>; children: ReactNode }) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-3">
      <dt className="flex shrink-0 items-center gap-2 text-muted">
        <Icon className="size-4" />
        {label}
      </dt>
      <dd className="min-w-0 truncate text-right tabular-nums">{children}</dd>
    </div>
  );
}

// Whether the Discord bot answers. null means the deployment has no bot.
export function BotBadge({ ready }: { ready: boolean | null }) {
  if (ready === null) return <Badge>Not set up</Badge>;
  return <Badge tone={ready ? 'ok' : 'bad'}>{ready ? 'Answers' : 'Not available'}</Badge>;
}

// The server's load, memory and disk, the database, the API container, the bot and the job queue.
export function ServerPage() {
  const server = useServerHealth();
  const s = server.data;
  const memoryUsed = s?.memory ? s.memory.total - s.memory.available : null;
  return (
    <>
      <PageHeader title="Server" docs="codebase/operations" />
      {server.error ? <ErrorNote error={server.error} /> : null}
      {server.isLoading ? <PageSkeleton stats /> : null}
      {s ? (
        <div className="space-y-6">
          <StatGrid>
            <Stat
              label="Load (1 min)"
              value={s.load ? s.load[0].toFixed(2) : '-'}
              sub={s.cpus ? `${s.cpus} CPUs, ${s.load ? s.load.map((l) => l.toFixed(2)).join(' / ') : '-'}` : undefined}
              icon={<Cpu className="size-4" />}
            />
            <Stat
              label="Memory"
              value={used(memoryUsed, s.memory?.total)}
              sub={s.memory ? `${bytes(memoryUsed ?? 0)} of ${bytes(s.memory.total)}` : undefined}
              icon={<MemoryStick className="size-4" />}
            />
            <Stat
              label="Disk"
              value={used(s.disk?.used, s.disk?.total)}
              sub={s.disk ? `${bytes(s.disk.free)} free of ${bytes(s.disk.total)}` : undefined}
              icon={<HardDrive className="size-4" />}
            />
            <Stat
              label="Database"
              value={s.database_bytes != null ? bytes(s.database_bytes) : '-'}
              sub={s.database}
              icon={<Database className="size-4" />}
            />
          </StatGrid>
          <Card>
            <CardHeader title="Processes" />
            <dl className="grid grid-cols-1 gap-x-8 gap-y-3 p-4 text-sm sm:grid-cols-2">
              <Fact label="API container" icon={Activity}>
                {s.container.memory_used != null ? bytes(s.container.memory_used) : '-'}
                {s.container.memory_limit != null ? ` of ${bytes(s.container.memory_limit)}` : ', no memory cap'}
                {s.container.cpu_limit != null ? `, ${s.container.cpu_limit} CPUs` : ''}
              </Fact>
              <Fact label="Up" icon={Clock}>
                API {elapsed(s.container.process_uptime_seconds)}
                {s.uptime_seconds != null ? `, server ${elapsed(s.uptime_seconds)}` : ''}
              </Fact>
              <Fact label="Discord bot" icon={Bot}>
                <BotBadge ready={s.bot_ready} />
              </Fact>
              <Fact label="Jobs" icon={ListTodo}>
                {queueText(s)}
              </Fact>
            </dl>
          </Card>
        </div>
      ) : null}
    </>
  );
}
