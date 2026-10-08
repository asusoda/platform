import { Badge, Card, CardHeader, Dot, Empty, ErrorNote, Loading, PageHeader, Row } from '../components/ui';
import { deployTone, timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import { useOverview } from '../lib/queries';

export function AppsPage() {
  const { prefix } = useCurrentOrg();
  const { data, isLoading, error } = useOverview(prefix);
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorNote error={error ?? 'No data'} />;
  const { apps } = data.sections.apps;
  const knowledge = data.sections.knowledge;
  return (
    <>
      <PageHeader title="Apps and knowledge" description="App deploys on RunPod and the sources agents search." />
      <Card>
        <CardHeader title="Apps" hint="Deployed by a pipeline with an apps:deploy token" />
        {apps.length ? (
          apps.map((app) => (
            <Row key={app.name}>
              <Dot tone={deployTone(app.status)} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{app.name}</div>
                <div className="truncate text-xs text-muted">{app.error ?? app.repo ?? 'no repository'}</div>
              </div>
              <span className="font-mono text-xs">{app.tag ?? '-'}</span>
              <Badge tone={deployTone(app.status)}>{app.status ?? 'not deployed'}</Badge>
              <span className="hidden w-20 text-right text-xs text-muted sm:block">{timeAgo(app.deployed_at)}</span>
            </Row>
          ))
        ) : (
          <Empty>No apps. Register one with PUT /api/apps/&lt;name&gt; and an apps:manage token.</Empty>
        )}
      </Card>
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <Card className="p-4">
          <div className="text-xs text-muted">Sources</div>
          <div className="mt-2 text-2xl font-semibold tabular-nums">{knowledge.sources}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted">Crawled on a schedule</div>
          <div className="mt-2 text-2xl font-semibold tabular-nums">{knowledge.crawled}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted">Failing crawls</div>
          <div className={`mt-2 text-2xl font-semibold tabular-nums ${knowledge.failing.length ? 'text-bad' : ''}`}>
            {knowledge.failing.length}
          </div>
        </Card>
      </div>
      {knowledge.failing.length ? (
        <Card className="mt-6">
          <CardHeader title="Failing crawls" />
          {knowledge.failing.map((source) => (
            <Row key={source.key}>
              <span className="font-mono text-xs">{source.key}</span>
              <span className="min-w-0 flex-1 truncate text-xs text-muted">{source.error}</span>
            </Row>
          ))}
        </Card>
      ) : null}
    </>
  );
}
