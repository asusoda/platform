import { CalendarClock, Cpu } from 'lucide-react';
import { Badge, Card, CardHeader, EmptyState, ErrorNote, Mono, PageHeader, PageSkeleton, Table, Td, Th, Tr } from '../components/ui';
import { duration, timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import { useOverview } from '../lib/queries';

export function ComputePage() {
  const { prefix } = useCurrentOrg();
  const { data, isLoading, error } = useOverview(prefix);
  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorNote error={error ?? 'No data'} />;
  const { pods, sessions } = data.sections.compute;
  const names = new Map(pods.map((pod) => [pod.pod_id, pod.name]));
  const next = new Map<string, string>();
  for (const s of [...sessions].sort((a, b) => a.start_at.localeCompare(b.start_at))) {
    if (!next.has(s.pod_id)) next.set(s.pod_id, s.start_at);
  }
  return (
    <>
      <PageHeader
        title="Compute"
        description="Pods on the organization's RunPod account. Members connect with the compute CLI."
      />
      <div className="grid gap-6">
        <Card>
          <CardHeader title="Pods" hint={`${pods.length} pods`} />
          {pods.length ? (
            <Table>
              <thead>
                <tr>
                  <Th>Name</Th>
                  <Th className="hidden sm:table-cell">Pod ID</Th>
                  <Th className="hidden md:table-cell">Next session</Th>
                  <Th className="text-right">Access</Th>
                </tr>
              </thead>
              <tbody>
                {pods.map((pod) => (
                  <Tr key={pod.pod_id}>
                    <Td>
                      <div className="font-medium">{pod.name}</div>
                      <Mono className="sm:hidden">{pod.pod_id}</Mono>
                    </Td>
                    <Td className="hidden sm:table-cell">
                      <Mono>{pod.pod_id}</Mono>
                    </Td>
                    <Td className="hidden text-xs whitespace-nowrap text-muted tabular-nums md:table-cell">
                      {next.has(pod.pod_id) ? timeAgo(next.get(pod.pod_id)) : 'none scheduled'}
                    </Td>
                    <Td className="text-right">
                      <Badge tone={pod.public ? 'ok' : 'muted'}>{pod.public ? 'All members' : 'Listed members'}</Badge>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <EmptyState icon={Cpu} title="No pods">
              Officers create them from the web app or with <Mono>POST /api/compute/{prefix}/pods</Mono>.
            </EmptyState>
          )}
        </Card>
        <Card>
          <CardHeader title="Scheduled sessions" hint="Pods start before a session and stop after it" />
          {sessions.length ? (
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
                {sessions.map((s) => (
                  <Tr key={`${s.pod_id}-${s.start_at}`}>
                    <Td>
                      <div className="font-medium">{s.title ?? 'Session'}</div>
                      <Mono className="sm:hidden">{s.pod_id}</Mono>
                    </Td>
                    <Td className="hidden sm:table-cell">
                      <div className="text-sm">{names.get(s.pod_id) ?? s.pod_id}</div>
                      <Mono>{s.pod_id}</Mono>
                    </Td>
                    <Td className="text-right text-xs whitespace-nowrap text-muted tabular-nums">{timeAgo(s.start_at)}</Td>
                    <Td className="hidden text-right text-xs whitespace-nowrap text-muted tabular-nums sm:table-cell">
                      {duration(s.start_at, s.stop_at)}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <EmptyState icon={CalendarClock}>No upcoming sessions.</EmptyState>
          )}
        </Card>
      </div>
    </>
  );
}
