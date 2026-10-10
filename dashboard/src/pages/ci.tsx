import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, GitBranch } from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Dot,
  EmptyState,
  ErrorNote,
  Field,
  PageHeader,
  PageSkeleton,
  Textarea,
} from '../components/ui';
import { send } from '../lib/api';
import { runTone, timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import { useCi } from '../lib/queries';

export function CiPage() {
  const { prefix } = useCurrentOrg();
  const client = useQueryClient();
  const ci = useCi(prefix);
  const [repos, setRepos] = useState('');
  useEffect(() => {
    if (ci.data) setRepos(ci.data.repos.map((r) => r.repo).join('\n'));
  }, [ci.data]);
  const save = useMutation({
    mutationFn: () =>
      send(`/api/dashboard/${prefix}/ci/repos`, 'PUT', {
        repos: repos.split(/[\s,]+/).filter(Boolean),
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['ci', prefix] }),
  });

  if (ci.isLoading) return <PageSkeleton />;

  return (
    <>
      <PageHeader title="CI runs" description="Latest GitHub Actions runs for the organization's repositories." />
      {ci.error ? (
        <div className="mb-4">
          <ErrorNote error={ci.error} />
        </div>
      ) : null}
      <div className="grid gap-6">
        {ci.data?.repos.map((repo) => (
          <Card key={repo.repo}>
            <CardHeader
              title={
                <a
                  className="inline-flex items-center gap-1.5 font-mono text-[13px] hover:underline"
                  href={`https://github.com/${repo.repo}/actions`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {repo.repo}
                  <ExternalLink className="size-3 text-muted" />
                </a>
              }
            />
            {repo.error ? (
              <div className="p-4">
                <ErrorNote error={repo.error} />
              </div>
            ) : repo.runs.length ? (
              repo.runs.map((run, i) => (
                <a
                  key={`${run.url}-${i}`}
                  href={run.url ?? undefined}
                  target="_blank"
                  rel="noreferrer"
                  className="flex min-h-12 items-center gap-3 border-b border-line px-4 py-2.5 transition-colors last:border-0 hover:bg-panel-2/50"
                >
                  <Dot tone={runTone(run.status, run.conclusion)} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm">{run.title}</div>
                    <div className="mt-0.5 truncate text-xs text-muted">
                      {run.workflow} · <span className="font-mono">{run.branch}</span> · {run.event}
                    </div>
                  </div>
                  <Badge tone={runTone(run.status, run.conclusion)}>{run.conclusion ?? run.status}</Badge>
                  <span className="hidden w-16 text-right text-xs text-muted tabular-nums sm:block">
                    {timeAgo(run.started_at)}
                  </span>
                </a>
              ))
            ) : (
              <EmptyState>No runs.</EmptyState>
            )}
          </Card>
        ))}
        {ci.data && !ci.data.repos.length ? (
          <Card>
            <EmptyState icon={GitBranch} title="No repositories">
              List the repositories below to see their latest runs here.
            </EmptyState>
          </Card>
        ) : null}
        <Card>
          <CardHeader title="Repositories" hint="Private repositories need the github_token secret under Settings." />
          <form
            className="space-y-4 p-4"
            onSubmit={(e) => {
              e.preventDefault();
              save.mutate();
            }}
          >
            <Field label="One owner/name per line">
              <Textarea
                className="font-mono"
                value={repos}
                onChange={(e) => setRepos(e.target.value)}
                placeholder={'your-org/website\nyour-org/api'}
              />
            </Field>
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="primary" disabled={save.isPending}>
                Save
              </Button>
              {save.error ? <ErrorNote error={save.error} /> : null}
            </div>
          </form>
        </Card>
      </div>
    </>
  );
}
