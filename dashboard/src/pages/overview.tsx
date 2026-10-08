import { AlertTriangle, Bot, Coins, Cpu, GitBranch, Users } from 'lucide-react';
import { Link } from 'react-router';
import { ActivityList } from '../components/activity-list';
import { Badge, Card, CardHeader, Dot, Empty, ErrorNote, Loading, PageHeader, Row, Stat } from '../components/ui';
import { compact, deployTone, runTone, timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import { useCi, useOverview } from '../lib/queries';

export function OverviewPage() {
  const { prefix } = useCurrentOrg();
  const { data, isLoading, error } = useOverview(prefix);
  const ci = useCi(prefix);
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorNote error={error ?? 'No data'} />;
  const s = data.sections;
  const runs = (ci.data?.repos ?? []).flatMap((r) => r.runs.slice(0, 1).map((run) => ({ repo: r.repo, ...run })));

  return (
    <>
      <PageHeader
        title={data.organization.name}
        description={`Everything running for ${data.organization.prefix}, refreshed ${timeAgo(data.generated_at)}.`}
      />

      {data.problems.length ? (
        <Card className="mb-6 border-bad/40">
          <CardHeader title={<span className="flex items-center gap-2 text-bad"><AlertTriangle className="size-4" /> Needs attention</span>} />
          {data.problems.map((p) => (
            <Row key={`${p.module}-${p.subject}`}>
              <Badge tone="bad">{p.module}</Badge>
              <span className="font-mono text-xs">{p.subject}</span>
              <span className="min-w-0 flex-1 truncate text-sm text-muted">{p.message}</span>
            </Row>
          ))}
        </Card>
      ) : null}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Members" value={compact(s.members.total)} icon={<Users className="size-4" />} />
        <Stat
          label="Points"
          value={compact(s.points.total)}
          sub={`${compact(s.points.last_30_days)} in the last 30 days`}
          icon={<Coins className="size-4" />}
        />
        <Stat
          label="Pods"
          value={s.compute.pods.length}
          sub={`${s.compute.sessions.length} upcoming sessions`}
          icon={<Cpu className="size-4" />}
        />
        <Stat
          label="Agent conversations"
          value={compact(s.agents.active_7_days)}
          sub={`${s.agents.members_7_days} members this week`}
          icon={<Bot className="size-4" />}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Modules"
            hint="Optional modules for this organization"
            action={<Link to="settings" className="text-xs text-muted hover:text-fg">Change</Link>}
          />
          <div className="grid gap-px bg-line sm:grid-cols-2">
            {data.modules.map((m) => (
              <div key={m.name} className="flex items-start gap-3 bg-panel px-4 py-3">
                <span className="mt-1.5"><Dot tone={m.enabled ? 'ok' : 'muted'} /></span>
                <div className="min-w-0">
                  <div className="text-sm font-medium">{m.name}</div>
                  <div className="text-xs text-muted">{m.description}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="CI" action={<Link to="ci" className="text-xs text-muted hover:text-fg">All runs</Link>} />
          {runs.length ? (
            runs.map((run) => (
              <a key={run.repo} href={run.url ?? undefined} target="_blank" rel="noreferrer" className="block hover:bg-panel-2">
                <Row>
                  <Dot tone={runTone(run.status, run.conclusion)} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm">{run.repo}</div>
                    <div className="truncate text-xs text-muted">{run.workflow} · {run.branch}</div>
                  </div>
                  <span className="text-xs text-muted">{timeAgo(run.started_at)}</span>
                </Row>
              </a>
            ))
          ) : (
            <Empty>
              <GitBranch className="mx-auto mb-2 size-5" />
              Add repositories in <Link to="ci" className="underline">CI runs</Link>.
            </Empty>
          )}
        </Card>

        <Card>
          <CardHeader title="Apps" hint="Deploys on RunPod" action={<Link to="apps" className="text-xs text-muted hover:text-fg">Details</Link>} />
          {s.apps.apps.length ? (
            s.apps.apps.map((app) => (
              <Row key={app.name}>
                <Dot tone={deployTone(app.status)} />
                <span className="flex-1 truncate text-sm">{app.name}</span>
                <span className="font-mono text-xs text-muted">{app.tag ?? 'not deployed'}</span>
              </Row>
            ))
          ) : (
            <Empty>No apps registered.</Empty>
          )}
        </Card>

        <Card>
          <CardHeader title="Alert feeds" action={<Link to="alerts" className="text-xs text-muted hover:text-fg">Manage</Link>} />
          {s.alerts.feeds.length ? (
            s.alerts.feeds.map((f) => (
              <Row key={f.key}>
                <Dot tone={!f.enabled ? 'muted' : f.last_error ? 'bad' : 'ok'} />
                <span className="flex-1 truncate text-sm">{f.key}</span>
                <span className="text-xs text-muted">{f.posted_7_days} this week</span>
              </Row>
            ))
          ) : (
            <Empty>No alert feeds.</Empty>
          )}
        </Card>

        <Card>
          <CardHeader title="Upcoming sessions" action={<Link to="compute" className="text-xs text-muted hover:text-fg">Compute</Link>} />
          {s.compute.sessions.length ? (
            s.compute.sessions.slice(0, 5).map((session) => (
              <Row key={`${session.pod_id}-${session.start_at}`}>
                <span className="flex-1 truncate text-sm">{session.title ?? session.pod_id}</span>
                <span className="text-xs text-muted">{timeAgo(session.start_at)}</span>
              </Row>
            ))
          ) : (
            <Empty>No sessions scheduled.</Empty>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Recent changes" action={<Link to="activity" className="text-xs text-muted hover:text-fg">Audit log</Link>} />
          <ActivityList entries={data.activity.slice(0, 8)} empty="No changes recorded yet." />
        </Card>

        <Card>
          <CardHeader title="Jobs" hint="Background runs" />
          <ActivityList entries={data.jobs.slice(0, 8)} empty="No job runs recorded for this organization." />
        </Card>
      </div>

      <p className="mt-8 text-xs text-muted">
        Store: {s.storefront.products} products, {s.storefront.pending_orders} pending orders. Knowledge: {s.knowledge.sources} sources.
        Tokens: {s.tokens.tokens.length} app and agent, {s.tokens.cli_tokens} CLI.
      </p>
    </>
  );
}
