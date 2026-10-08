import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { OrgMark } from '../components/org-mark';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  cx,
  ErrorNote,
  Field,
  Input,
  PageHeader,
  PageSkeleton,
  Row,
  SkeletonRows,
  Switch,
} from '../components/ui';
import { api, send } from '../lib/api';
import { isHexColor, isHttpsUrl, readableForeground } from '../lib/branding';
import { timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import { useBranding } from '../lib/queries';
import type { Branding, ModuleState, SecretState } from '../lib/types';

function BrandingForm({ prefix, name, saved }: { prefix: string; name: string; saved: Branding }) {
  const client = useQueryClient();
  const [logo, setLogo] = useState(saved.logo_url ?? '');
  const [accent, setAccent] = useState(saved.accent_color ?? '');
  const logoOk = !logo || isHttpsUrl(logo);
  const accentOk = !accent || isHexColor(accent);
  const changed = logo !== (saved.logo_url ?? '') || accent !== (saved.accent_color ?? '');
  const save = useMutation({
    mutationFn: () => send<Branding>(`/api/dashboard/${prefix}/branding`, 'PUT', { logo_url: logo, accent_color: accent }),
    onSuccess: (data) => {
      client.setQueryData(['branding', prefix], data);
      client.invalidateQueries({ queryKey: ['overview', prefix] });
    },
  });
  const preview = accent && accentOk ? { background: accent, color: readableForeground(accent) } : undefined;
  return (
    <form
      className="grid gap-6 p-4 md:grid-cols-[minmax(0,1fr)_260px]"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="space-y-5">
        <Field label="Logo URL" hint={logoOk ? 'An https image URL. Square images fit best. Leave empty for the initial.' : 'Must be an https URL.'}>
          <Input value={logo} onChange={(e) => setLogo(e.target.value.trim())} placeholder="https://example.org/logo.png" aria-invalid={!logoOk} />
        </Field>
        <Field label="Accent color" hint={accentOk ? 'Used for primary buttons and the initial when there is no logo. Leave empty for the neutral default.' : 'Must be a hex color like #1f6feb.'}>
          <div className="flex gap-2">
            <input
              type="color"
              aria-label="Pick accent color"
              value={accent && accentOk ? accent : '#808080'}
              onChange={(e) => setAccent(e.target.value)}
              className="h-9 w-12 shrink-0 cursor-pointer rounded-md border border-line bg-panel p-1 shadow-xs"
            />
            <Input value={accent} onChange={(e) => setAccent(e.target.value.trim())} placeholder="#1f6feb" className="font-mono" aria-invalid={!accentOk} />
            {accent ? (
              <Button type="button" variant="ghost" onClick={() => setAccent('')}>
                Default
              </Button>
            ) : null}
          </div>
        </Field>
        <div className="flex items-center gap-3 border-t border-line pt-4">
          <Button variant="primary" disabled={!changed || !logoOk || !accentOk || save.isPending}>
            Save branding
          </Button>
          {save.isSuccess && !changed ? <span className="text-xs text-muted">Saved</span> : null}
        </div>
        {save.error ? <ErrorNote error={save.error} /> : null}
      </div>
      <div className="space-y-3 rounded-lg border border-dashed border-line-strong bg-bg p-3">
        <div className="font-mono text-[11px] tracking-wider text-muted uppercase">Preview</div>
        <div className="flex items-center gap-2.5 rounded-lg border border-line bg-panel p-2 shadow-xs">
          <OrgMark key={logo} name={name} logoUrl={logoOk ? logo : null} className="size-8" />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">{name}</span>
            <span className="block truncate font-mono text-xs text-muted">{prefix}</span>
          </span>
        </div>
        <span
          className={cx('inline-flex h-8 items-center rounded-md px-3 text-sm font-medium shadow-xs', !preview && 'bg-fg text-bg')}
          style={preview}
        >
          Primary action
        </span>
      </div>
    </form>
  );
}

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
      <div className="min-w-0 flex-1 basis-56">
        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          {secret.name}
          <Badge tone={secret.set ? 'ok' : 'muted'}>{secret.set ? `set ${timeAgo(secret.updated_at)}` : 'not set'}</Badge>
        </div>
        <div className="mt-1 text-xs text-muted">{secret.description}</div>
      </div>
      <form
        className="flex w-full gap-2 sm:w-auto"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <Input type="password" value={value} onChange={(e) => setValue(e.target.value)} placeholder="New value" className="min-w-0 sm:w-48" aria-label={`New value for ${secret.name}`} />
        <Button disabled={!value || save.isPending}>Save</Button>
        {secret.set ? (
          <Button type="button" variant="danger" onClick={() => clear.mutate()}>
            Remove
          </Button>
        ) : null}
      </form>
      {save.error ? (
        <div className="w-full">
          <ErrorNote error={save.error} />
        </div>
      ) : null}
    </div>
  );
}

export function SettingsPage() {
  const { org, prefix } = useCurrentOrg();
  const client = useQueryClient();
  const branding = useBranding(prefix);
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
  if (!org) return <PageSkeleton />;
  return (
    <>
      <PageHeader title="Settings" description="Branding, modules and secrets for this organization." />
      <Card className="mb-6">
        <CardHeader title="Branding" hint="The logo and accent color officers see in this dashboard." />
        {branding.error ? <div className="p-4"><ErrorNote error={branding.error} /></div> : null}
        {branding.data ? (
          <BrandingForm key={JSON.stringify(branding.data)} prefix={prefix} name={org.name} saved={branding.data} />
        ) : branding.isLoading ? (
          <SkeletonRows rows={3} />
        ) : null}
      </Card>
      <Card>
        <CardHeader title="Modules" hint="A module that is off returns 404 for this organization." />
        {modules.isLoading ? <SkeletonRows /> : null}
        {modules.data?.modules.map((m) => (
          <Row key={m.name}>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{m.name}</div>
              <div className="mt-0.5 text-xs text-muted">{m.description}</div>
            </div>
            <Switch checked={m.enabled} onChange={() => toggle.mutate(m)} disabled={toggle.isPending} label={m.name} />
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
