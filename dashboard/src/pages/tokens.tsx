import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, Plus } from 'lucide-react';
import { useState } from 'react';
import { Badge, Button, Card, CardHeader, Empty, ErrorNote, Field, Input, Loading, PageHeader, Row } from '../components/ui';
import { api, send } from '../lib/api';
import { timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import type { MachineToken } from '../lib/types';

type TokenList = { tokens: MachineToken[]; scopes: Record<string, string> };

function NewToken({ orgId, scopes, onDone }: { orgId: number; scopes: Record<string, string>; onDone: () => void }) {
  const client = useQueryClient();
  const [name, setName] = useState('');
  const [kind, setKind] = useState('agent');
  const [chosen, setChosen] = useState<string[]>([]);
  const [value, setValue] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => send<{ token: string }>(`/api/organizations/${orgId}/tokens`, 'POST', { name, kind, scopes: chosen }),
    onSuccess: (body) => {
      setValue(body.token);
      client.invalidateQueries({ queryKey: ['tokens', orgId] });
    },
  });
  if (value) {
    return (
      <Card className="mb-6 p-4">
        <p className="text-sm">Copy the token now. It is not shown again.</p>
        <div className="mt-3 flex gap-2">
          <Input readOnly value={value} className="font-mono" />
          <Button onClick={() => navigator.clipboard.writeText(value)}>
            <Copy className="size-4" />
          </Button>
        </div>
        <Button className="mt-3" variant="ghost" onClick={onDone}>
          Done
        </Button>
      </Card>
    );
  }
  return (
    <Card className="mb-6">
      <CardHeader title="New token" />
      <form
        className="space-y-4 p-4"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="club-agent" required />
          </Field>
          <Field label="Kind">
            <select className="h-9 w-full rounded-lg border border-line bg-panel px-3 text-sm" value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="agent">agent</option>
              <option value="app">app</option>
            </select>
          </Field>
        </div>
        <fieldset className="grid gap-2 sm:grid-cols-2">
          {Object.entries(scopes).map(([scope, description]) => (
            <label key={scope} className="flex items-start gap-2 rounded-lg border border-line p-2.5 text-sm">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={chosen.includes(scope)}
                onChange={(e) => setChosen(e.target.checked ? [...chosen, scope] : chosen.filter((s) => s !== scope))}
              />
              <span>
                <span className="block font-mono text-xs">{scope}</span>
                <span className="block text-xs text-muted">{description}</span>
              </span>
            </label>
          ))}
        </fieldset>
        <div className="flex items-center gap-2">
          <Button variant="primary" disabled={create.isPending || !chosen.length}>
            Create token
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

export function TokensPage() {
  const { org } = useCurrentOrg();
  const client = useQueryClient();
  const [adding, setAdding] = useState(false);
  const list = useQuery({
    queryKey: ['tokens', org?.id],
    queryFn: () => api<TokenList>(`/api/organizations/${org!.id}/tokens`),
    enabled: Boolean(org),
  });
  const revoke = useMutation({
    mutationFn: (id: number) => send(`/api/organizations/${org!.id}/tokens/${id}`, 'DELETE'),
    onSuccess: () => client.invalidateQueries({ queryKey: ['tokens', org?.id] }),
  });
  return (
    <>
      <PageHeader
        title="Tokens"
        description="Machine tokens let apps, agents and pipelines call the platform with the scopes you give them."
        action={
          <Button variant="primary" onClick={() => setAdding(true)} disabled={!list.data}>
            <Plus className="size-4" /> New token
          </Button>
        }
      />
      {adding && org && list.data ? <NewToken orgId={org.id} scopes={list.data.scopes} onDone={() => setAdding(false)} /> : null}
      {list.error ? <ErrorNote error={list.error} /> : null}
      {list.isLoading ? (
        <Loading />
      ) : (
        <Card>
          {list.data?.tokens.length ? (
            list.data.tokens.map((t) => (
              <Row key={t.id}>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    {t.name} <Badge>{t.kind}</Badge>
                  </div>
                  <div className="truncate font-mono text-xs text-muted">{t.scopes.join(' ')}</div>
                </div>
                <span className="hidden font-mono text-xs text-muted sm:block">{t.display}…</span>
                <span className="hidden w-24 text-right text-xs text-muted sm:block">used {timeAgo(t.last_used_at)}</span>
                <Button
                  variant="danger"
                  onClick={() => {
                    if (confirm(`Revoke ${t.name}? Anything using it stops working.`)) revoke.mutate(t.id);
                  }}
                >
                  Revoke
                </Button>
              </Row>
            ))
          ) : (
            <Empty>No active tokens.</Empty>
          )}
        </Card>
      )}
    </>
  );
}
