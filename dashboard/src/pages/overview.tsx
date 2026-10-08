import { AlertTriangle, BellRing, Boxes, Bot, CalendarClock, Coins, Cpu, GitBranch, Users } from 'lucide-react';
import { Link } from 'react-router';
import { ActivityList } from '../components/activity-list';
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
  quietLink,
  Row,
  Stat,
} from '../components/ui';
import { compact, deployTone, runTone, timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import { useCi, useOverview } from '../lib/queries';

export function OverviewPage() {
  const { prefix } = useCurrentOrg();
  const { data, isLoading, error } = useOverview(prefix);
  const ci = useCi(prefix);
  if (isLoading) return <PageSkeleton stats />;
  if (error || !data) return <ErrorNote error={error ?? 'No data'} />;
  const s = data.sections;
  const runs = (ci.data?.repos ?? []).flatMap((r) => r.runs.slice(0, 1).map((run) => ({ repo: r.repo, ...run })));
  const enabled = data.modules.filter((m) => m.enabled).length;

  return (
    <>
      <PageHeader
        title={data.organization.name}
        description={`Everything running for ${data.organization.prefix}, refreshed ${timeAgo(data.generated_at)}.`}
      />

      {data.problems.length ? (
        <Card className="mb-6 border-bad/30">
          <CardHeader
            title={
              <span className="flex items-center gap-2 text-bad">
                <AlertTriangle className="size-4" /> Needs attention
              </span>
            }
          />
          {data.problems.map((p) => (
            <Row key={`${p.module}-${p.subject}`} className="flex-wrap sm:flex-nowrap">
              <Badge tone="bad">{p.module}</Badge>
              <Mono className="text-fg">{p.subject}</Mono>
              <span className="min-w-0 flex-1 basis-full truncate text-sm text-muted sm:basis-auto">{p.message}</span>
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
            hint={`${enabled} of ${data.modules.length} on for this organization`}
            action={
              <Link to="settings" className={quietLink}>
                Change
              </Link>
            }
          />
          <div className="grid gap-px bg-line sm:grid-cols-2">
            {data.modules.map((m) => (
              <div key={m.name} className="flex items-start gap-3 bg-panel px-4 py-3">
                <span className="mt-1.5">
                  <Dot tone={m.enabled ? 'ok' : 'muted'} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className={m.enabled ? 'text-sm font-medium' : 'text-sm font-medium text-muted'}>{m.name}</span>
                    <span className="text-xs text-muted">{m.enabled ? 'On' : 'Off'}</span>
                  </div>
                  <div className="mt-0.5 text-xs text-muted">{m.description}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="CI"
            hint="Latest run per repository"
            action={
              <Link to="activity?tab=ci" className={quietLink}>
                All runs
              </Link>
            }
          />
          {runs.length ? (
            runs.map((run) => (
              <a
                key={run.repo}
                href={run.url ?? undefined}
                target="_blank"
                rel="noreferrer"
                className="block transition-colors hover:bg-panel-2/50"
              >
                <Row>
                  <Dot tone={runTone(run.status, run.conclusion)} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm">{run.repo}</div>
                    <div className="truncate text-xs text-muted">
                      {run.workflow} · {run.branch}
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-muted tabular-nums">{timeAgo(run.started_at)}</span>
                </Row>
              </a>
            ))
          ) : (
            <EmptyState icon={GitBranch}>
              Add repositories in{' '}
              <Link to="activity?tab=ci" className="text-fg underline underline-offset-2">
                CI runs
              </Link>
              .
            </EmptyState>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Apps"
            hint="Deploys on RunPod"
            action={
              <Link to="apps" className={quietLink}>
                Details
              </Link>
            }
          />
          {s.apps.apps.length ? (
            s.apps.apps.map((app) => (
              <Row key={app.name}>
                <Dot tone={deployTone(app.status)} />
                <span className="flex-1 truncate text-sm">{app.name}</span>
                <Mono>{app.tag ?? 'not deployed'}</Mono>
              </Row>
            ))
          ) : (
            <EmptyState icon={Boxes}>No apps registered.</EmptyState>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Alert feeds"
            hint="Posts in the last 7 days"
            action={
              <Link to="alerts" className={quietLink}>
                Manage
              </Link>
            }
          />
          {s.alerts.feeds.length ? (
            s.alerts.feeds.map((f) => (
              <Row key={f.key}>
                <Dot tone={!f.enabled ? 'muted' : f.last_error ? 'bad' : 'ok'} />
                <span className="flex-1 truncate text-sm">{f.key}</span>
                <span className="text-xs text-muted tabular-nums">{f.posted_7_days} this week</span>
              </Row>
            ))
          ) : (
            <EmptyState icon={BellRing}>No alert feeds.</EmptyState>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Upcoming sessions"
            hint="Pods start before each session"
            action={
              <Link to="compute" className={quietLink}>
                Compute
              </Link>
            }
          />
          {s.compute.sessions.length ? (
            s.compute.sessions.slice(0, 5).map((session) => (
              <Row key={`${session.pod_id}-${session.start_at}`}>
                <span className="flex-1 truncate text-sm">{session.title ?? session.pod_id}</span>
                <span className="text-xs text-muted tabular-nums">{timeAgo(session.start_at)}</span>
              </Row>
            ))
          ) : (
            <EmptyState icon={CalendarClock}>No sessions scheduled.</EmptyState>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader
            title="Recent changes"
            action={
              <Link to="activity" className={quietLink}>
                Audit log
              </Link>
            }
          />
          <ActivityList entries={data.activity.slice(0, 8)} empty="No changes recorded yet." />
        </Card>

        <Card>
          <CardHeader title="Jobs" hint="Background runs" />
          <ActivityList entries={data.jobs.slice(0, 8)} empty="No job runs recorded for this organization." />
        </Card>
      </div>

      <p className="mt-8 border-t border-line pt-4 text-xs text-muted">
        Store: {s.storefront.products} products, {s.storefront.pending_orders} pending orders. Knowledge:{' '}
        {s.knowledge.sources} sources. Tokens: {s.tokens.tokens.length} app and agent, {s.tokens.cli_tokens} CLI.
      </p>
    </>
  );
}
