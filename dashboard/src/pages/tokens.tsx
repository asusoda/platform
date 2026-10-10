import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Copy, KeyRound, Plus } from 'lucide-react';
import { useState } from 'react';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Code,
  cx,
  EmptyState,
  ErrorNote,
  Field,
  Input,
  Mono,
  PageHeader,
  Select,
  SkeletonRows,
  Table,
  Td,
  Th,
  Tr,
} from '../components/ui';
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
  const [copied, setCopied] = useState(false);
  const create = useMutation({
    mutationFn: () => send<{ token: string }>(`/api/organizations/${orgId}/tokens`, 'POST', { name, kind, scopes: chosen }),
    onSuccess: (body) => {
      setValue(body.token);
      client.invalidateQueries({ queryKey: ['tokens', orgId] });
    },
  });
  if (value) {
    return (
      <Card className="mb-6">
        <CardHeader title="Token created" hint="Copy the token now. It is not shown again." />
        <div className="space-y-4 p-4">
          <div className="flex gap-2">
            <Input readOnly value={value} className="font-mono" aria-label="New token" />
            <Button
              size="icon"
              aria-label="Copy token"
              onClick={() => {
                navigator.clipboard.writeText(value);
                setCopied(true);
              }}
            >
              {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
            </Button>
          </div>
          <Button onClick={onDone}>Done</Button>
        </div>
      </Card>
    );
  }
  return (
    <Card className="mb-6">
      <CardHeader title="New token" hint="Give the token only the scopes it needs." />
      <form
        className="space-y-5 p-4"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Name">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="club-agent" required />
          </Field>
          <Field label="Kind">
            <Select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="agent">agent</option>
              <option value="app">app</option>
            </Select>
          </Field>
        </div>
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium">Scopes</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {Object.entries(scopes).map(([scope, description]) => {
              const on = chosen.includes(scope);
              return (
                <label
                  key={scope}
                  className={cx(
                    'flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-sm transition-colors has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring',
                    on ? 'border-fg/40 bg-panel-2' : 'border-line hover:bg-panel-2/50',
                  )}
                >
                  <input
                    type="checkbox"
                    className="mt-0.5 size-4 accent-current"
                    checked={on}
                    onChange={(e) => setChosen(e.target.checked ? [...chosen, scope] : chosen.filter((s) => s !== scope))}
                  />
                  <span className="min-w-0">
                    <span className="block font-mono text-xs">{scope}</span>
                    <span className="mt-0.5 block text-xs text-muted">{description}</span>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>
        <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
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
      {list.error ? (
        <div className="mb-4">
          <ErrorNote error={list.error} />
        </div>
      ) : null}
      <Card>
        {list.isLoading || !org ? (
          <SkeletonRows />
        ) : list.data?.tokens.length ? (
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th className="hidden md:table-cell">Token</Th>
                <Th className="hidden lg:table-cell">Last used</Th>
                <Th>
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {list.data.tokens.map((t) => (
                <Tr key={t.id}>
                  <Td className="w-full max-w-0 py-3">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-medium">{t.name}</span>
                      <Badge>{t.kind}</Badge>
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {t.scopes.map((scope) => (
                        <Code key={scope} className="text-muted">
                          {scope}
                        </Code>
                      ))}
                    </div>
                  </Td>
                  <Td className="hidden whitespace-nowrap md:table-cell">
                    <Mono>{t.display}…</Mono>
                  </Td>
                  <Td className="hidden text-xs whitespace-nowrap text-muted tabular-nums lg:table-cell">
                    {timeAgo(t.last_used_at)}
                  </Td>
                  <Td className="text-right">
                    <Button
                      variant="danger"
                      onClick={() => {
                        if (confirm(`Revoke ${t.name}? Anything using it stops working.`)) revoke.mutate(t.id);
                      }}
                    >
                      Revoke
                    </Button>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <EmptyState icon={KeyRound} title="No active tokens">
            Create a token for an app, an agent or a pipeline.
          </EmptyState>
        )}
      </Card>
    </>
  );
}
