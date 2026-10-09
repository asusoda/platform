import { Bug, ExternalLink } from 'lucide-react';
import { useNavigate } from 'react-router';
import { Badge, Button, Card, CardHeader, Dot, EmptyState, ErrorNote, SkeletonRows } from '../../components/ui';
import { compact, type Tone, timeAgo } from '../../lib/format';
import { useCurrentOrg } from '../../lib/org';
import { useSentryIssues } from '../../lib/queries';

const LEVEL_TONE: Record<string, Tone> = { fatal: 'bad', error: 'bad', warning: 'warn', info: 'muted', debug: 'muted' };

// Unresolved issues of the org's Sentry project. Shown on the Activity page.
export function SentryErrors() {
  const { prefix } = useCurrentOrg();
  const errors = useSentryIssues(prefix);
  const navigate = useNavigate();

  if (errors.isLoading) {
    return (
      <Card>
        <SkeletonRows rows={6} />
      </Card>
    );
  }
  if (errors.error) return <ErrorNote error={errors.error} />;
  const data = errors.data;
  if (!data?.configured) {
    return (
      <Card>
        <EmptyState
          icon={Bug}
          title="Sentry is not connected"
          action={
            <Button onClick={() => navigate(`/${prefix}/integrations`)}>Connect Sentry</Button>
          }
        >
          Connect the Sentry card on the Integrations page to see the unresolved errors here.
        </EmptyState>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Unresolved errors"
        hint="From Sentry, last 14 days. Open an error in Sentry for its stack trace."
        action={
          data.project_url ? (
            <Button variant="ghost" onClick={() => window.open(data.project_url ?? '', '_blank', 'noopener')}>
              Open Sentry
              <ExternalLink className="size-3.5" />
            </Button>
          ) : null
        }
      />
      {data.error ? (
        <div className="p-4">
          <ErrorNote error={data.error} />
        </div>
      ) : data.issues.length ? (
        data.issues.map((issue) => {
          const tone = LEVEL_TONE[issue.level ?? ''] ?? 'muted';
          return (
            <a
              key={issue.id}
              href={issue.url ?? undefined}
              target="_blank"
              rel="noreferrer"
              className="flex min-h-12 items-center gap-3 border-b border-line px-4 py-2.5 transition-colors last:border-0 hover:bg-panel-2/50"
            >
              <Dot tone={tone} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm">{issue.title}</div>
                <div className="mt-0.5 truncate text-xs text-muted">
                  <span className="font-mono">{issue.short_id}</span>
                  {issue.culprit ? ` · ${issue.culprit}` : null}
                </div>
              </div>
              <Badge tone={tone}>{compact(issue.count)} events</Badge>
              <span className="hidden w-20 text-right text-xs text-muted tabular-nums sm:block">
                {timeAgo(issue.last_seen)}
              </span>
            </a>
          );
        })
      ) : (
        <EmptyState icon={Bug} title="No unresolved errors">
          Sentry has no open issues for this project.
        </EmptyState>
      )}
    </Card>
  );
}
