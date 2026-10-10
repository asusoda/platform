import { Boxes } from 'lucide-react';
import {
  Badge,
  Card,
  CardHeader,
  Dot,
  EmptyState,
  ErrorNote,
  Mono,
  PageHeader,
  PageSkeleton,
  Row,
  Stat,
  Table,
  Td,
  Th,
  Tr,
} from '../components/ui';
import { deployTone, timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import { useOverview } from '../lib/queries';

export function AppsPage() {
  const { prefix } = useCurrentOrg();
  const { data, isLoading, error } = useOverview(prefix);
  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorNote error={error ?? 'No data'} />;
  const { apps } = data.sections.apps;
  const knowledge = data.sections.knowledge;
  return (
    <>
      <PageHeader title="Apps and knowledge" description="App deploys on RunPod and the sources agents search." />
      <Card>
        <CardHeader title="Apps" hint="Deployed by a pipeline with an apps:deploy token" />
        {apps.length ? (
          <Table>
            <thead>
              <tr>
                <Th>App</Th>
                <Th className="hidden sm:table-cell">Tag</Th>
                <Th>Status</Th>
                <Th className="hidden text-right sm:table-cell">Deployed</Th>
              </tr>
            </thead>
            <tbody>
              {apps.map((app) => (
                <Tr key={app.name}>
                  <Td className="max-w-0 w-full">
                    <div className="flex items-center gap-2.5">
                      <Dot tone={deployTone(app.status)} />
                      <div className="min-w-0">
                        <div className="truncate font-medium">{app.name}</div>
                        <div className={app.error ? 'truncate text-xs text-bad' : 'truncate text-xs text-muted'}>
                          {app.error ?? app.repo ?? 'no repository'}
                        </div>
                      </div>
                    </div>
                  </Td>
                  <Td className="hidden whitespace-nowrap sm:table-cell">
                    <Mono className="text-fg">{app.tag ?? '-'}</Mono>
                  </Td>
                  <Td>
                    <Badge tone={deployTone(app.status)}>{app.status ?? 'not deployed'}</Badge>
                  </Td>
                  <Td className="hidden text-right text-xs whitespace-nowrap text-muted tabular-nums sm:table-cell">
                    {timeAgo(app.deployed_at)}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <EmptyState icon={Boxes} title="No apps">
            Register one with <Mono>PUT /api/apps/&lt;name&gt;</Mono> and an <Mono>apps:manage</Mono> token.
          </EmptyState>
        )}
      </Card>
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <Stat label="Sources" value={knowledge.sources} />
        <Stat label="Crawled on a schedule" value={knowledge.crawled} />
        <Stat
          label="Failing crawls"
          value={<span className={knowledge.failing.length ? 'text-bad' : undefined}>{knowledge.failing.length}</span>}
        />
      </div>
      {knowledge.failing.length ? (
        <Card className="mt-6">
          <CardHeader title="Failing crawls" />
          {knowledge.failing.map((source) => (
            <Row key={source.key}>
              <Mono className="text-fg">{source.key}</Mono>
              <span className="min-w-0 flex-1 truncate text-xs text-muted">{source.error}</span>
            </Row>
          ))}
        </Card>
      ) : null}
    </>
  );
}
