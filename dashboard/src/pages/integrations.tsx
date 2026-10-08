import { useMutation, useQueryClient } from '@tanstack/react-query';
import { BookOpen, Brain, CalendarDays, Cloud, FileText, Plug, PlugZap } from 'lucide-react';
import { type ComponentType, useState } from 'react';
import { Link } from 'react-router';
import { DiscordIcon, GitHubIcon } from '../components/brand-icons';
import {
  Badge,
  Button,
  Card,
  cx,
  Dialog,
  ErrorNote,
  Field,
  FormActions,
  Input,
  PageHeader,
  PageSkeleton,
  Spinner,
  Textarea,
} from '../components/ui';
import { send } from '../lib/api';
import { timeAgo } from '../lib/format';
import { docsPage } from '../lib/links';
import { useCurrentOrg } from '../lib/org';
import { useIntegrations } from '../lib/queries';
import type { Integration, IntegrationList, IntegrationTest } from '../lib/types';

const ICONS: Record<string, ComponentType<{ className?: string }>> = {
  discord: DiscordIcon,
  github: GitHubIcon,
  google: CalendarDays,
  notion: FileText,
  runpod: Cloud,
  embeddings: Brain,
};

// The module names the API sends, with their label and dashboard page.
const MODULES: Record<string, { label: string; path?: string }> = {
  auth: { label: 'Sign-in' },
  calendar: { label: 'Calendar', path: 'calendar' },
  compute: { label: 'Compute', path: 'compute' },
  dashboard: { label: 'CI runs', path: 'activity?tab=ci' },
  games: { label: 'Games' },
  knowledge: { label: 'Knowledge', path: 'knowledge' },
  leetcode: { label: 'LeetCode', path: 'leetcode' },
  runpod: { label: 'Apps', path: 'apps' },
};

function StateBadge({ i }: { i: Integration }) {
  if (i.source === 'org') return <Badge tone="ok">Connected</Badge>;
  if (i.source === 'deployment') return <Badge tone="active">Deployment default</Badge>;
  return <Badge tone="warn">Not connected</Badge>;
}

function KeysForm({ prefix, i, onDone }: { prefix: string; i: Integration; onDone: () => void }) {
  const client = useQueryClient();
  const [values, setValues] = useState<Record<string, string>>({});
  const save = useMutation({
    mutationFn: (fields: Record<string, string | null>) =>
      send<IntegrationList>(`/api/dashboard/${prefix}/integrations/${i.key}`, 'PUT', { fields }),
    onSuccess: (list) => {
      client.setQueryData(['integrations', prefix], list);
      onDone();
    },
  });
  const filled = Object.fromEntries(Object.entries(values).filter(([, v]) => v.trim()));
  const anySet = i.fields.some((f) => f.set);
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (Object.keys(filled).length) save.mutate(filled);
      }}
    >
      {i.fields.map((f) => (
        <Field key={f.name} label={f.label} hint={f.set ? `Saved ${timeAgo(f.updated_at)}. Leave empty to keep it. ${f.hint}` : f.hint}>
          {f.kind === 'json' ? (
            <div className="space-y-2">
              <Textarea
                rows={5}
                className="font-mono text-xs"
                value={values[f.name] ?? ''}
                placeholder={f.set ? 'Saved' : '{ "type": "service_account", ... }'}
                onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
              />
              <input
                type="file"
                accept="application/json,.json"
                aria-label={`${f.label} file`}
                className="text-xs text-muted file:mr-2 file:cursor-pointer file:rounded-md file:border file:border-line file:bg-panel file:px-2 file:py-1 file:text-xs"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (file) setValues({ ...values, [f.name]: await file.text() });
                }}
              />
            </div>
          ) : (
            <Input
              type="password"
              autoComplete="off"
              value={values[f.name] ?? ''}
              placeholder={f.set ? 'Saved' : ''}
              onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
            />
          )}
        </Field>
      ))}
      <FormActions error={save.error}>
        <Button variant="primary" disabled={!Object.keys(filled).length || save.isPending}>
          {save.isPending ? <Spinner className="size-3.5" /> : null}
          Save
        </Button>
        {anySet ? (
          <Button
            type="button"
            variant="danger"
            disabled={save.isPending}
            onClick={() => save.mutate(Object.fromEntries(i.fields.map((f) => [f.name, null])))}
          >
            Disconnect
          </Button>
        ) : null}
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

function IntegrationCard({ prefix, i, canSave }: { prefix: string; i: Integration; canSave: boolean }) {
  const Icon = ICONS[i.key] ?? Plug;
  const [editing, setEditing] = useState(false);
  const test = useMutation({
    mutationFn: () => send<IntegrationTest>(`/api/dashboard/${prefix}/integrations/${i.key}/test`, 'POST'),
  });
  const saved = i.fields.filter((f) => f.set && f.updated_at).map((f) => f.updated_at as string);
  return (
    <Card className="flex flex-col">
      <div className="flex items-start gap-3 p-4">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-line bg-panel-2/60">
          <Icon className="size-[18px]" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold">{i.title}</h2>
            <StateBadge i={i} />
          </div>
          <p className="mt-1 text-sm text-pretty text-muted">{i.description}</p>
          {i.source === 'deployment' && i.editable ? (
            <p className="mt-1 text-xs text-muted">The deployment's key is in use. Save your own to replace it for this org.</p>
          ) : null}
          {saved.length ? <p className="mt-1 text-xs text-muted">Saved {timeAgo(saved.sort().at(-1) as string)}.</p> : null}
        </div>
      </div>
      {i.used_by.length ? (
        <div className="flex flex-wrap items-center gap-1.5 px-4 pb-3 text-xs text-muted">
          Used by
          {i.used_by.map((m) => {
            const mod = MODULES[m] ?? { label: m };
            return mod.path ? (
              <Link key={m} to={`/${prefix}/${mod.path}`} className="rounded-md border border-line px-1.5 py-0.5 text-fg transition-colors hover:bg-panel-2">
                {mod.label}
              </Link>
            ) : (
              <span key={m} className="rounded-md border border-line px-1.5 py-0.5">
                {mod.label}
              </span>
            );
          })}
        </div>
      ) : null}
      {test.data ? (
        <div className={cx('mx-4 mb-3 animate-in rounded-md px-3 py-2 text-xs', test.data.ok ? 'bg-ok/10 text-ok' : 'bg-bad/10 text-bad')} role="status">
          {test.data.message}
        </div>
      ) : null}
      {test.error ? (
        <div className="mx-4 mb-3">
          <ErrorNote error={test.error} />
        </div>
      ) : null}
      <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-line px-4 py-3">
        {i.editable ? (
          <Button variant={i.source === 'org' ? 'secondary' : 'primary'} disabled={!canSave} onClick={() => setEditing(true)}>
            <PlugZap className="size-4" /> {i.source === 'org' ? 'Edit keys' : 'Connect'}
          </Button>
        ) : null}
        {i.testable ? (
          <Button variant="ghost" disabled={test.isPending} onClick={() => test.mutate()}>
            {test.isPending ? <Spinner className="size-3.5" /> : null} Test
          </Button>
        ) : null}
        {i.docs ? (
          <a href={docsPage(i.docs)} target="_blank" rel="noreferrer" className="ml-auto flex items-center gap-1 text-xs text-muted transition-colors hover:text-fg">
            <BookOpen className="size-3.5" /> Docs
          </a>
        ) : null}
      </div>
      <Dialog open={editing} onClose={() => setEditing(false)} title={`Connect ${i.title}`} description="Keys are encrypted on the API and never shown again.">
        <KeysForm prefix={prefix} i={i} onDone={() => setEditing(false)} />
      </Dialog>
    </Card>
  );
}

// The outside services the org connects: their keys, where the keys come from, and the modules that use them.
export function IntegrationsPage() {
  const { prefix } = useCurrentOrg();
  const { data, isLoading, error } = useIntegrations(prefix);
  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorNote error={error ?? 'No data'} />;
  const connected = data.integrations.filter((i) => i.source).length;
  return (
    <>
      <PageHeader
        title="Integrations"
        description={`Outside services that modules use. ${connected} of ${data.integrations.length} connected.`}
      />
      {!data.secrets_key ? (
        <div className="mb-4">
          <ErrorNote error="SECRETS_KEY is not set on the API, so keys cannot be saved." />
        </div>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        {data.integrations.map((i) => (
          <IntegrationCard key={i.key} prefix={prefix} i={i} canSave={data.secrets_key} />
        ))}
      </div>
    </>
  );
}
