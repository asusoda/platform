import { Card, CardHeader, Empty, ErrorNote, Loading, PageHeader, Row, Badge } from '../components/ui';
import { timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import { useOverview } from '../lib/queries';

export function ComputePage() {
  const { prefix } = useCurrentOrg();
  const { data, isLoading, error } = useOverview(prefix);
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorNote error={error ?? 'No data'} />;
  const { pods, sessions } = data.sections.compute;
  return (
    <>
      <PageHeader
        title="Compute"
        description="Pods on the organization's RunPod account. Members connect with the godfather CLI: pip install godfather-cli."
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Pods" hint={`${pods.length} pods`} />
          {pods.length ? (
            pods.map((pod) => (
              <Row key={pod.pod_id}>
                <span className="flex-1 truncate text-sm">{pod.name}</span>
                <span className="font-mono text-xs text-muted">{pod.pod_id}</span>
                <Badge tone={pod.public ? 'accent' : 'muted'}>{pod.public ? 'all members' : 'listed members'}</Badge>
              </Row>
            ))
          ) : (
            <Empty>No pods. Officers create them from the web app or POST /api/compute/{prefix}/pods.</Empty>
          )}
        </Card>
        <Card>
          <CardHeader title="Scheduled sessions" hint="Pods start before a session and stop after it" />
          {sessions.length ? (
            sessions.map((s) => (
              <Row key={`${s.pod_id}-${s.start_at}`}>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm">{s.title ?? 'Session'}</div>
                  <div className="font-mono text-xs text-muted">{s.pod_id}</div>
                </div>
                <div className="text-right text-xs text-muted">
                  <div>starts {timeAgo(s.start_at)}</div>
                  <div>stops {timeAgo(s.stop_at)}</div>
                </div>
              </Row>
            ))
          ) : (
            <Empty>No upcoming sessions.</Empty>
          )}
        </Card>
      </div>
    </>
  );
}
