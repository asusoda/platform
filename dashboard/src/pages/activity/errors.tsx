import { Bug, CheckCheck } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { ErrorList } from '../../components/error-list';
import { Badge, Button, Card, CardHeader, EmptyState, ErrorNote, Select, SkeletonRows } from '../../components/ui';
import { useCurrentOrg } from '../../lib/org';
import { type ErrorStatus, useErrorChange, useErrors } from '../../lib/queries';

// The org's errors from the Platform error log. Shown on the Activity page. The Webhooks page sets where new errors go.
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
      <p className="text-xs text-muted">
        {list.data?.webhook_set ? 'A webhook sends new errors to a channel.' : 'No webhook sends errors to a channel.'}{' '}
        <Link to={`/${prefix}/webhooks`} className="text-fg underline-offset-2 hover:underline">
          Set webhooks
        </Link>
      </p>
    </div>
  );
}
