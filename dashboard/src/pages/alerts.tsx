import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Play, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Badge, Button, Card, CardHeader, Dot, Empty, ErrorNote, Field, Input, Loading, PageHeader, Switch } from '../components/ui';
import { api, send } from '../lib/api';
import { timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import type { AlertFeed } from '../lib/types';

type Draft = { key: string; kind: AlertFeed['kind']; repo: string; label: string; webhook: string; every: string };
const EMPTY: Draft = { key: '', kind: 'github_jobs', repo: '', label: 'Internship', webhook: '', every: '3' };

function NewFeed({ prefix, onDone }: { prefix: string; onDone: () => void }) {
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const client = useQueryClient();
  const create = useMutation({
    mutationFn: () =>
      send(`/api/alerts/${prefix}/feeds/${draft.key}`, 'PUT', {
        kind: draft.kind,
        webhook_url: draft.webhook,
        every_hours: Number(draft.every),
        config: draft.kind === 'github_jobs' ? { repo: draft.repo, label: draft.label } : {},
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['alerts', prefix] });
      onDone();
    },
  });
  const set = (k: keyof Draft) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  return (
    <Card className="mb-6">
      <CardHeader title="New feed" hint="The first run records what is listed now and posts only what comes after." />
      <form
        className="grid gap-4 p-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <Field label="Key" hint="Lowercase letters, digits and dashes">
          <Input value={draft.key} onChange={set('key')} placeholder="internships" required />
        </Field>
        <Field label="Kind">
          <select
            className="h-9 w-full rounded-lg border border-line bg-panel px-3 text-sm"
            value={draft.kind}
            onChange={set('kind')}
          >
            <option value="github_jobs">Job table in a GitHub README</option>
            <option value="hackathons">Hackathons</option>
          </select>
        </Field>
        {draft.kind === 'github_jobs' ? (
          <>
            <Field label="Repository" hint="owner/name">
              <Input value={draft.repo} onChange={set('repo')} placeholder="vanshb03/Summer2026-Internships" required />
            </Field>
            <Field label="Label" hint="Word in each post title">
              <Input value={draft.label} onChange={set('label')} />
            </Field>
          </>
        ) : null}
        <Field label="Discord webhook URL" hint="Stored encrypted and never shown again">
          <Input value={draft.webhook} onChange={set('webhook')} placeholder="https://discord.com/api/webhooks/..." required />
        </Field>
        <Field label="Every (hours)">
          <Input type="number" min={1} max={168} value={draft.every} onChange={set('every')} />
        </Field>
        <div className="flex items-center gap-2 sm:col-span-2">
          <Button variant="primary" disabled={create.isPending}>
            Create feed
          </Button>
          <Button type="button" variant="ghost" onClick={onDone}>
            Cancel
          </Button>
          {create.error ? <ErrorNote error={create.error} /> : null}
        </div>
      </form>
    </Card>
  );
}

export function AlertsPage() {
  const { prefix } = useCurrentOrg();
  const client = useQueryClient();
  const [adding, setAdding] = useState(false);
  const feeds = useQuery({
    queryKey: ['alerts', prefix],
    queryFn: () => api<{ feeds: AlertFeed[] }>(`/api/alerts/${prefix}/feeds`),
  });
  const refresh = () => client.invalidateQueries({ queryKey: ['alerts', prefix] });
  const toggle = useMutation({
    mutationFn: (f: AlertFeed) => send(`/api/alerts/${prefix}/feeds/${f.key}`, 'PUT', { enabled: !f.enabled }),
    onSuccess: refresh,
  });
  const run = useMutation({ mutationFn: (key: string) => send(`/api/alerts/${prefix}/feeds/${key}/run`, 'POST', {}), onSuccess: refresh });
  const remove = useMutation({ mutationFn: (key: string) => send(`/api/alerts/${prefix}/feeds/${key}`, 'DELETE'), onSuccess: refresh });

  return (
    <>
      <PageHeader
        title="Alerts"
        description="Job listings and hackathons posted to Discord channels through webhooks."
        action={
          <Button variant="primary" onClick={() => setAdding(true)}>
            <Plus className="size-4" /> New feed
          </Button>
        }
      />
      {adding ? <NewFeed prefix={prefix} onDone={() => setAdding(false)} /> : null}
      {feeds.error ? <ErrorNote error={feeds.error} /> : null}
      {feeds.isLoading ? (
        <Loading />
      ) : (
        <Card>
          {feeds.data?.feeds.length ? (
            feeds.data.feeds.map((f) => (
              <div key={f.key} className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 last:border-0">
                <Dot tone={!f.enabled ? 'muted' : f.last_error ? 'bad' : f.seeded_at ? 'ok' : 'warn'} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    {f.key}
                    <Badge>{f.kind === 'github_jobs' ? String(f.config.repo ?? '') : 'hackathons'}</Badge>
                  </div>
                  <div className="truncate text-xs text-muted">
                    {f.last_error ? <span className="text-bad">{f.last_error}</span> : `every ${f.every_hours}h · last run ${timeAgo(f.last_run_at)} · ${f.posted} posted`}
                  </div>
                </div>
                <Switch checked={f.enabled} onChange={() => toggle.mutate(f)} />
                <Button variant="ghost" title="Run now" onClick={() => run.mutate(f.key)}>
                  <Play className="size-4" />
                </Button>
                <Button
                  variant="ghost"
                  title="Delete"
                  onClick={() => {
                    if (confirm(`Delete feed ${f.key} and its webhook?`)) remove.mutate(f.key);
                  }}
                >
                  <Trash2 className="size-4 text-bad" />
                </Button>
              </div>
            ))
          ) : (
            <Empty>No feeds yet.</Empty>
          )}
        </Card>
      )}
    </>
  );
}
