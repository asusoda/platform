import { CalendarClock, Cpu, KeyRound, Plus } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorNote,
  Mono,
  PageHeader,
  SkeletonRows,
  Stat,
  StatGrid,
  Table,
  Td,
  Th,
  Tr,
} from '../../components/ui';
import { duration, timeAgo, when } from '../../lib/format';
import { useCurrentOrg } from '../../lib/org';
import { useOverview } from '../../lib/queries';
import type { Pod } from '../../lib/types';
import { FilesDialog } from './files';
import { NewPodDialog } from './new-pod';
import { AccessDialog, type PodDialog, PodsTable, TerminateDialog } from './pods';
import { SessionsDialog } from './sessions';
import { costLabel, isMissingKey, usePods } from './shared';

function MissingKey({ prefix }: { prefix: string }) {
  return (
    <EmptyState
      icon={KeyRound}
      title="Add the org's RunPod API key"
      action={
        <Link to={`/${prefix}/settings#secrets`} className="inline-flex h-8 items-center rounded-md bg-accent px-3 text-sm font-medium text-accent-fg shadow-xs hover:opacity-85">
          Open settings
        </Link>
      }
    >
      Pods run on the org's own RunPod account. Save its API key as the secret <Mono>runpod_api_key</Mono> under
      Settings, Secrets.
    </EmptyState>
  );
}

function Upcoming({ prefix, pods, open }: { prefix: string; pods: Pod[]; open: (d: PodDialog) => void }) {
  const overview = useOverview(prefix);
  const sessions = [...(overview.data?.sections.compute.sessions ?? [])].sort((a, b) => a.start_at.localeCompare(b.start_at));
  const byId = new Map(pods.map((p) => [p.id, p]));
  return (
    <Card>
      <CardHeader title="Upcoming sessions" hint="Pods start 10 minutes before a session and stop when it ends" />
      {overview.isLoading ? (
        <SkeletonRows rows={3} />
      ) : sessions.length ? (
        <Table>
          <thead>
            <tr>
              <Th>Session</Th>
              <Th className="hidden sm:table-cell">Pod</Th>
              <Th className="text-right">Starts</Th>
              <Th className="hidden text-right sm:table-cell">Length</Th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => {
              const pod = byId.get(s.pod_id);
              return (
                <Tr key={`${s.pod_id}-${s.start_at}`}>
                  <Td className="w-full max-w-0">
                    <div className="truncate font-medium">{s.title ?? 'Session'}</div>
                    <div className="truncate text-xs text-muted sm:hidden">{pod?.name ?? s.pod_id}</div>
                  </Td>
                  <Td className="hidden whitespace-nowrap sm:table-cell">
                    {pod ? (
                      <button
                        type="button"
                        className="cursor-pointer rounded-sm text-sm hover:underline"
                        onClick={() => open({ kind: 'sessions', pod })}
                      >
                        {pod.name}
                      </button>
                    ) : (
                      <Mono>{s.pod_id}</Mono>
                    )}
                  </Td>
                  <Td className="text-right text-xs whitespace-nowrap text-muted tabular-nums" title={when(s.start_at)}>
                    {timeAgo(s.start_at)}
                  </Td>
                  <Td className="hidden text-right text-xs whitespace-nowrap text-muted tabular-nums sm:table-cell">
                    {duration(s.start_at, s.stop_at)}
                  </Td>
                </Tr>
              );
            })}
          </tbody>
        </Table>
      ) : (
        <EmptyState icon={CalendarClock}>No upcoming sessions. Add one from a pod's Sessions.</EmptyState>
      )}
    </Card>
  );
}

export function ComputePage() {
  const { prefix } = useCurrentOrg();
  const pods = usePods(prefix);
  const [creating, setCreating] = useState(false);
  const [dialog, setDialog] = useState<PodDialog | null>(null);
  const overview = useOverview(prefix);
  const missingKey = isMissingKey(pods.error);
  const list = pods.data ?? [];
  const running = list.filter((p) => p.status === 'RUNNING');
  const spend = running.reduce((sum, p) => sum + (Number(p.cost_per_hour) || 0), 0);
  const upcoming = overview.data?.sections.compute.sessions.length;
  // The dialog follows the latest copy of its pod from the list.
  const current = dialog ? { ...dialog, pod: list.find((p) => p.id === dialog.pod.id) ?? dialog.pod } : null;
  const close = () => setDialog(null);

  return (
    <>
      <PageHeader
        title="Compute"
        description="GPU and CPU pods on the org's RunPod account. Members connect with the compute CLI."
        action={
          <Button variant="primary" onClick={() => setCreating(true)} disabled={missingKey}>
            <Plus className="size-4" /> New pod
          </Button>
        }
      />
      {missingKey ? null : (
        <StatGrid className="mb-6">
          <Stat label="Pods" value={pods.data ? list.length : '-'} />
          <Stat label="Running" value={pods.data ? running.length : '-'} sub={pods.data ? `${list.length - running.length} stopped` : undefined} />
          <Stat label="Spend while running" value={pods.data ? (costLabel(spend) ?? '-') : '-'} sub="Running pods only" />
          <Stat label="Upcoming sessions" value={upcoming ?? '-'} />
        </StatGrid>
      )}
      <div className="grid gap-6">
        <Card>
          <CardHeader
            title="Pods"
            hint={pods.data ? `${list.length} ${list.length === 1 ? 'pod' : 'pods'} · status from RunPod, refreshed every 15 seconds` : undefined}
            action={pods.isFetching && pods.data ? <Badge tone="active">Refreshing</Badge> : null}
          />
          {pods.isLoading ? (
            <SkeletonRows />
          ) : missingKey ? (
            <MissingKey prefix={prefix} />
          ) : pods.error ? (
            <div className="p-4">
              <ErrorNote error={pods.error} />
            </div>
          ) : list.length ? (
            <PodsTable prefix={prefix} pods={list} open={setDialog} />
          ) : (
            <EmptyState
              icon={Cpu}
              title="No pods yet"
              action={
                <Button variant="primary" onClick={() => setCreating(true)}>
                  <Plus className="size-4" /> New pod
                </Button>
              }
            >
              Create a pod for a workshop or a project team. Members connect to it with the compute CLI.
            </EmptyState>
          )}
        </Card>
        {missingKey ? null : <Upcoming prefix={prefix} pods={list} open={setDialog} />}
      </div>

      {creating ? <NewPodDialog prefix={prefix} onClose={() => setCreating(false)} /> : null}
      {current?.kind === 'access' ? <AccessDialog key={current.pod.id} prefix={prefix} pod={current.pod} onClose={close} /> : null}
      {current?.kind === 'terminate' ? <TerminateDialog prefix={prefix} pod={current.pod} onClose={close} /> : null}
      {current?.kind === 'sessions' ? <SessionsDialog prefix={prefix} pod={current.pod} onClose={close} /> : null}
      {current?.kind === 'files' ? <FilesDialog prefix={prefix} pod={current.pod} onClose={close} /> : null}
    </>
  );
}
