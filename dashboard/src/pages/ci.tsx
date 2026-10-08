import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Badge, Button, Card, CardHeader, Dot, Empty, ErrorNote, Field, Loading, PageHeader } from '../components/ui';
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

  return (
    <>
      <PageHeader title="CI runs" description="Latest GitHub Actions runs for the organization's repositories." />
      {ci.isLoading ? <Loading /> : null}
      {ci.error ? <ErrorNote error={ci.error} /> : null}
      <div className="grid gap-6">
        {ci.data?.repos.map((repo) => (
          <Card key={repo.repo}>
            <CardHeader
              title={
                <a className="hover:underline" href={`https://github.com/${repo.repo}/actions`} target="_blank" rel="noreferrer">
                  {repo.repo}
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
                  className="flex items-center gap-3 border-b border-line px-4 py-2.5 last:border-0 hover:bg-panel-2"
                >
                  <Dot tone={runTone(run.status, run.conclusion)} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm">{run.title}</div>
                    <div className="truncate text-xs text-muted">
                      {run.workflow} · {run.branch} · {run.event}
                    </div>
                  </div>
                  <Badge tone={runTone(run.status, run.conclusion)}>{run.conclusion ?? run.status}</Badge>
                  <span className="hidden w-16 text-right text-xs text-muted sm:block">{timeAgo(run.started_at)}</span>
                </a>
              ))
            ) : (
              <Empty>No runs.</Empty>
            )}
          </Card>
        ))}
        <Card>
          <CardHeader title="Repositories" hint="Private repositories need the github_token secret under Settings." />
          <form
            className="space-y-3 p-4"
            onSubmit={(e) => {
              e.preventDefault();
              save.mutate();
            }}
          >
            <Field label="One owner/name per line">
              <textarea
                className="min-h-28 w-full rounded-lg border border-line bg-panel p-3 font-mono text-sm outline-none focus:border-accent"
                value={repos}
                onChange={(e) => setRepos(e.target.value)}
                placeholder={'your-org/website\nyour-org/api'}
              />
            </Field>
            <div className="flex items-center gap-3">
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
