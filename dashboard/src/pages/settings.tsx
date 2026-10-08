import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Badge, Button, Card, CardHeader, ErrorNote, Input, Loading, PageHeader, Row, Switch } from '../components/ui';
import { api, send } from '../lib/api';
import { timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import type { ModuleState, SecretState } from '../lib/types';

function SecretRow({ orgId, secret }: { orgId: number; secret: SecretState & { updated_at?: string | null } }) {
  const client = useQueryClient();
  const [value, setValue] = useState('');
  const refresh = () => client.invalidateQueries({ queryKey: ['secrets', orgId] });
  const save = useMutation({
    mutationFn: () => send(`/api/organizations/${orgId}/secrets/${secret.name}`, 'PUT', { value }),
    onSuccess: () => {
      setValue('');
      refresh();
    },
  });
  const clear = useMutation({ mutationFn: () => send(`/api/organizations/${orgId}/secrets/${secret.name}`, 'DELETE'), onSuccess: refresh });
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 last:border-0">
      <div className="min-w-48 flex-1">
        <div className="flex items-center gap-2 font-mono text-xs">
          {secret.name}
          <Badge tone={secret.set ? 'ok' : 'muted'}>{secret.set ? `set ${timeAgo(secret.updated_at)}` : 'not set'}</Badge>
        </div>
        <div className="text-xs text-muted">{secret.description}</div>
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <Input type="password" value={value} onChange={(e) => setValue(e.target.value)} placeholder="New value" className="w-48" />
        <Button disabled={!value || save.isPending}>Save</Button>
        {secret.set ? (
          <Button type="button" variant="danger" onClick={() => clear.mutate()}>
            Remove
          </Button>
        ) : null}
      </form>
      {save.error ? <ErrorNote error={save.error} /> : null}
    </div>
  );
}

export function SettingsPage() {
  const { org } = useCurrentOrg();
  const client = useQueryClient();
  const modules = useQuery({
    queryKey: ['modules', org?.id],
    enabled: Boolean(org),
    queryFn: () => api<{ modules: ModuleState[] }>(`/api/organizations/${org!.id}/modules`),
  });
  const secrets = useQuery({
    queryKey: ['secrets', org?.id],
    enabled: Boolean(org),
    queryFn: () => api<{ configured: boolean; secrets: SecretState[] }>(`/api/organizations/${org!.id}/secrets`),
  });
  const toggle = useMutation({
    mutationFn: (m: ModuleState) => send(`/api/organizations/${org!.id}/modules`, 'PUT', { modules: { [m.name]: !m.enabled } }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['modules', org?.id] });
      client.invalidateQueries({ queryKey: ['overview'] });
    },
  });
  if (!org) return <Loading />;
  return (
    <>
      <PageHeader title="Settings" description="Modules and secrets for this organization." />
      <Card>
        <CardHeader title="Modules" hint="A module that is off returns 404 for this organization." />
        {modules.isLoading ? <Loading /> : null}
        {modules.data?.modules.map((m) => (
          <Row key={m.name}>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{m.name}</div>
              <div className="text-xs text-muted">{m.description}</div>
            </div>
            <Switch checked={m.enabled} onChange={() => toggle.mutate(m)} disabled={toggle.isPending} />
          </Row>
        ))}
        {toggle.error ? <div className="p-4"><ErrorNote error={toggle.error} /></div> : null}
      </Card>
      <Card className="mt-6">
        <CardHeader title="Secrets" hint="Encrypted with the server's SECRETS_KEY. Values are never shown." />
        {secrets.data && !secrets.data.configured ? (
          <div className="p-4">
            <ErrorNote error="SECRETS_KEY is not set on the server, so secrets cannot be saved." />
          </div>
        ) : null}
        {secrets.data?.secrets.map((s) => <SecretRow key={s.name} orgId={org.id} secret={s} />)}
      </Card>
    </>
  );
}
