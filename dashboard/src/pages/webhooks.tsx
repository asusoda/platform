import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, Pencil, Plus, Send, Webhook as WebhookIcon } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  CheckOption,
  cx,
  DeleteButton,
  Dialog,
  Dot,
  EmptyState,
  ErrorNote,
  Field,
  FormActions,
  Input,
  Mono,
  PageHeader,
  Select,
  SkeletonRows,
  Spinner,
  Switch,
} from '../components/ui';
import { api, send } from '../lib/api';
import { timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import type { Webhook, WebhookList, WebhookTest } from '../lib/types';

type Draft = { name: string; kind: string; url: string; events: string[] };

// The form to add a webhook, or to change one. When it changes one, an empty URL keeps the saved URL.
function WebhookForm({ prefix, list, hook, onDone }: { prefix: string; list: WebhookList; hook: Webhook | null; onDone: () => void }) {
  const client = useQueryClient();
  const [draft, setDraft] = useState<Draft>({
    name: hook?.name ?? '',
    kind: hook?.kind ?? list.kinds[0]?.key ?? 'discord',
    url: '',
    events: hook?.events ?? ['errors'],
  });
  const save = useMutation({
    mutationFn: () => {
      const body = {
        name: draft.name,
        events: draft.events,
        ...(draft.url.trim() ? { url: draft.url.trim() } : {}),
      };
      return hook
        ? send(`/api/dashboard/${prefix}/webhooks/${hook.id}`, 'PUT', body)
        : send(`/api/dashboard/${prefix}/webhooks`, 'POST', {
            ...body,
            kind: draft.kind,
          });
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['webhooks', prefix] });
      onDone();
    },
  });
  const kind = list.kinds.find((k) => k.key === draft.kind);
  const toggle = (key: string, on: boolean) =>
    setDraft({
      ...draft,
      events: on ? [...draft.events, key] : draft.events.filter((e) => e !== key),
    });
  return (
    <form
      className="grid gap-5"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Name">
          <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Officer alerts" required />
        </Field>
        <Field label="Destination">
          <Select value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value })} disabled={Boolean(hook)}>
            {list.kinds.map((k) => (
              <option key={k.key} value={k.key}>
                {k.label}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field
        label={`${kind?.label ?? 'Webhook'} webhook URL`}
        hint="Channel settings > Integrations > Webhooks. The URL is stored encrypted and never shown again."
      >
        <Input
          type="url"
          value={draft.url}
          onChange={(e) => setDraft({ ...draft, url: e.target.value })}
          placeholder={hook ? 'Saved. Paste a new URL to replace it.' : kind?.example}
          required={!hook}
        />
      </Field>
      <fieldset className="grid gap-2">
        <legend className="mb-2 text-sm font-medium">Events</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {list.events.map((e) => (
            <CheckOption key={e.key} checked={draft.events.includes(e.key)} onChange={(on) => toggle(e.key, on)} title={e.label}>
              {e.description}
            </CheckOption>
          ))}
        </div>
      </fieldset>
      <FormActions error={save.error}>
        <Button variant="primary" disabled={save.isPending || !draft.events.length}>
          {hook ? 'Save' : 'Add webhook'}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

function WebhookRow({ prefix, hook, labels, onEdit }: { prefix: string; hook: Webhook; labels: Map<string, string>; onEdit: () => void }) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ['webhooks', prefix] });
  const toggle = useMutation({
    mutationFn: () =>
      send(`/api/dashboard/${prefix}/webhooks/${hook.id}`, 'PUT', {
        enabled: !hook.enabled,
      }),
    onSuccess: refresh,
  });
  const test = useMutation({
    mutationFn: () => send<WebhookTest>(`/api/dashboard/${prefix}/webhooks/${hook.id}/test`, 'POST'),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => send(`/api/dashboard/${prefix}/webhooks/${hook.id}`, 'DELETE'),
    onSuccess: refresh,
  });
  const error = toggle.error ?? test.error ?? remove.error;
  return (
    <div className="border-b border-line px-4 py-3 last:border-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <Dot tone={!hook.enabled ? 'muted' : hook.last_error ? 'bad' : 'ok'} />
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm font-medium">
            <span className="truncate">{hook.name}</span>
            <Badge>{hook.kind === 'discord' ? 'Discord' : hook.kind}</Badge>
            <Mono className="text-xs font-normal text-muted">{hook.url_hint}</Mono>
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {hook.events.map((key) => (
              <span key={key} className="rounded-md border border-line px-1.5 py-0.5 text-xs text-muted">
                {labels.get(key) ?? key}
              </span>
            ))}
          </div>
          <div className="mt-1.5 truncate text-xs text-muted">
            {hook.last_error ? (
              <span className="text-bad">{hook.last_error}</span>
            ) : hook.last_sent_at ? (
              `last message ${timeAgo(hook.last_sent_at)}`
            ) : (
              'no messages yet'
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Switch checked={hook.enabled} onChange={() => toggle.mutate()} label={`Webhook ${hook.name} on`} disabled={toggle.isPending} />
          <Button variant="ghost" disabled={test.isPending} onClick={() => test.mutate()}>
            {test.isPending ? <Spinner className="size-3.5" /> : <Send className="size-4" />} Send test
          </Button>
          <Button variant="ghost" size="icon" title="Edit" aria-label={`Edit ${hook.name}`} onClick={onEdit}>
            <Pencil className="size-4" />
          </Button>
          <DeleteButton label={`Delete ${hook.name}`} question={`Delete webhook ${hook.name}?`} onDelete={() => remove.mutate()} />
        </div>
      </div>
      {test.data ? (
        <div
          className={cx('mt-2 animate-in rounded-md px-3 py-2 text-xs', test.data.ok ? 'bg-ok/10 text-ok' : 'bg-bad/10 text-bad')}
          role="status"
        >
          {test.data.message}
        </div>
      ) : null}
      {error ? (
        <div className="mt-2">
          <ErrorNote error={error} />
        </div>
      ) : null}
    </div>
  );
}

function FeedsCard({ prefix, list }: { prefix: string; list: WebhookList }) {
  return (
    <Card>
      <CardHeader
        title="Alert feeds"
        hint="Job and hackathon feeds post to their own webhooks on a schedule."
        action={
          <Link to={`/${prefix}/alerts`} className="inline-flex items-center gap-1 text-xs text-muted transition-colors hover:text-fg">
            Open Alerts <ArrowRight className="size-3.5" />
          </Link>
        }
      />
      {list.feeds.length ? (
        list.feeds.map((f) => (
          <div key={f.key} className="flex items-center gap-3 border-b border-line px-4 py-2.5 text-sm last:border-0">
            <Dot tone={!f.enabled ? 'muted' : f.last_error ? 'bad' : 'ok'} />
            <span className="min-w-0 flex-1 truncate font-medium">{f.key}</span>
            <Badge>{f.kind === 'github_jobs' ? 'job list' : 'hackathons'}</Badge>
            <span className="hidden w-32 text-right text-xs text-muted sm:block">
              {f.enabled ? `ran ${timeAgo(f.last_run_at)}` : 'off'}
            </span>
          </div>
        ))
      ) : (
        <p className="px-4 py-3 text-sm text-muted">No alert feeds. Add one on the Alerts page.</p>
      )}
    </Card>
  );
}

export function WebhooksPage() {
  const { prefix } = useCurrentOrg();
  const [editing, setEditing] = useState<Webhook | 'new' | null>(null);
  const list = useQuery({
    queryKey: ['webhooks', prefix],
    queryFn: () => api<WebhookList>(`/api/dashboard/${prefix}/webhooks`),
  });
  const data = list.data;
  const labels = new Map((data?.events ?? []).map((e) => [e.key, e.label]));
  const hooks = data?.webhooks ?? [];

  return (
    <>
      <PageHeader
        title="Webhooks"
        description="Messages that Platform sends to your channels when events happen: errors, failed jobs, pods, deploys, orders and new members."
        action={
          <Button variant="primary" disabled={!data?.secrets_key} onClick={() => setEditing('new')}>
            <Plus className="size-4" /> New webhook
          </Button>
        }
      />
      {list.error ? (
        <div className="mb-4">
          <ErrorNote error={list.error} />
        </div>
      ) : null}
      {data && !data.secrets_key ? (
        <div className="mb-4 rounded-md bg-warn/10 px-3 py-2 text-sm text-warn" role="status">
          SECRETS_KEY is not set on the API, so webhook URLs cannot be saved.
        </div>
      ) : null}
      <div className="grid gap-6">
        <Card>
          <CardHeader title="Webhooks" hint={data ? `${hooks.length} webhooks` : undefined} />
          {list.isLoading ? (
            <SkeletonRows />
          ) : hooks.length ? (
            hooks.map((h) => <WebhookRow key={h.id} prefix={prefix} hook={h} labels={labels} onEdit={() => setEditing(h)} />)
          ) : (
            <EmptyState icon={WebhookIcon} title="No webhooks">
              Add a webhook to get a message in a channel when an event happens.
            </EmptyState>
          )}
        </Card>
        {data?.alerts ? <FeedsCard prefix={prefix} list={data} /> : null}
      </div>
      <Dialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? 'New webhook' : `Edit ${editing?.name ?? ''}`}
        description="Pick the events this webhook sends. Each event sends one message."
        wide
      >
        {data && editing !== null ? (
          <WebhookForm
            key={editing === 'new' ? 'new' : editing.id}
            prefix={prefix}
            list={data}
            hook={editing === 'new' ? null : editing}
            onDone={() => setEditing(null)}
          />
        ) : null}
      </Dialog>
    </>
  );
}
