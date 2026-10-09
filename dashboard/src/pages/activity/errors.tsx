import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Bug, CheckCheck } from 'lucide-react';
import { useState } from 'react';
import { ErrorList } from '../../components/error-list';
import { Badge, Button, Card, CardHeader, EmptyState, ErrorNote, Field, Input, Select, SkeletonRows } from '../../components/ui';
import { send } from '../../lib/api';
import { useCurrentOrg } from '../../lib/org';
import { type ErrorStatus, useErrorChange, useErrors } from '../../lib/queries';

// The org's errors from the Platform error log, and the Discord webhook for new ones. Shown on the Activity page.
export function ErrorsTab() {
  const { prefix } = useCurrentOrg();
  const [status, setStatus] = useState<ErrorStatus>('open');
  const list = useErrors(prefix, status);
  const change = useErrorChange(prefix);
  const errors = list.data?.errors ?? [];
  const run = (action: 'resolve' | 'reopen', ids: number[]) => change.mutate({ action, ids });

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader
          title={
            <span className="inline-flex items-center gap-2">
              Errors
              {list.data ? <Badge tone={list.data.open ? 'bad' : 'ok'}>{list.data.open} open</Badge> : null}
            </span>
          }
          hint="Errors of the API, bot, jobs, MCP server and this dashboard. Repeats add to one row. A resolved error opens again when it happens again."
          action={
            <div className="flex items-center gap-2">
              {status === 'open' && errors.length ? (
                <Button disabled={change.isPending} onClick={() => run('resolve', errors.map((e) => e.id))}>
                  <CheckCheck className="size-4" /> Resolve all
                </Button>
              ) : null}
              <Select value={status} onChange={(e) => setStatus(e.target.value as ErrorStatus)} aria-label="Status" className="h-8 w-32! text-xs">
                <option value="open">Open</option>
                <option value="resolved">Resolved</option>
              </Select>
            </div>
          }
        />
        {list.error ? (
          <div className="p-4">
            <ErrorNote error={list.error} />
          </div>
        ) : null}
        {change.error ? (
          <div className="p-4">
            <ErrorNote error={change.error} />
          </div>
        ) : null}
        {list.isLoading ? (
          <SkeletonRows rows={5} />
        ) : errors.length ? (
          <ErrorList errors={errors} onChange={run} busy={change.isPending} />
        ) : (
          <EmptyState icon={Bug} title={status === 'open' ? 'No open errors' : 'Nothing resolved'}>
            {status === 'open' ? 'Errors show here as they happen.' : 'Resolved errors show here until they are deleted after 90 days.'}
          </EmptyState>
        )}
      </Card>
      <WebhookCard set={Boolean(list.data?.webhook_set)} />
    </div>
  );
}

function WebhookCard({ set }: { set: boolean }) {
  const { prefix } = useCurrentOrg();
  const client = useQueryClient();
  const [url, setUrl] = useState('');
  const save = useMutation({
    mutationFn: (value: string | null) => send(`/api/dashboard/${prefix}/errors/webhook`, 'PUT', { url: value }),
    onSuccess: () => {
      setUrl('');
      client.invalidateQueries({ queryKey: ['errors', prefix] });
    },
  });
  return (
    <Card>
      <CardHeader
        title={
          <span className="inline-flex items-center gap-2">
            Discord alerts {set ? <Badge tone="ok">On</Badge> : <Badge tone="muted">Off</Badge>}
          </span>
        }
        hint="Each new error, and each resolved error that comes back, posts one message to this channel."
      />
      <form
        className="space-y-4 p-4"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate(url.trim());
        }}
      >
        <Field label="Discord webhook URL" hint="Channel settings > Integrations > Webhooks. The URL is stored encrypted and never shown again.">
          <Input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={set ? 'Saved. Paste a new URL to replace it.' : 'https://discord.com/api/webhooks/...'}
          />
        </Field>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary" disabled={save.isPending || !url.trim()}>
            Save
          </Button>
          {set ? (
            <Button type="button" variant="ghost" disabled={save.isPending} onClick={() => save.mutate(null)}>
              Turn off
            </Button>
          ) : null}
          {save.error ? <ErrorNote error={save.error} /> : null}
        </div>
      </form>
    </Card>
  );
}
