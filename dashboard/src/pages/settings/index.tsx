import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { type ReactNode, useEffect, useState } from 'react';
import { Badge, Card, CardHeader, cx, ErrorNote, PageHeader, PageSkeleton, Row, SkeletonRows, Switch } from '../../components/ui';
import { api, send } from '../../lib/api';
import { timeAgo } from '../../lib/format';
import { useCurrentOrg } from '../../lib/org';
import { useBranding, useModules, useOrganization } from '../../lib/queries';
import type { CalendarSettings, LeetCodeSettings, ModuleState, Organization, SecretState } from '../../lib/types';
import { BrandingForm } from './branding';
import { CalendarForm } from './calendar';
import { GeneralForm } from './general';
import { LeetCodeForm } from './leetcode';
import { SecretRow } from './secrets';

type Section = { id: string; label: string };

// The id of the section nearest the top of the viewport.
function useActiveSection(ids: string[]): string | undefined {
  const [active, setActive] = useState<string>();
  const key = ids.join(',');
  useEffect(() => {
    const seen = new Map<string, boolean>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) seen.set(entry.target.id, entry.isIntersecting);
        const first = key.split(',').find((id) => seen.get(id));
        if (first) setActive(first);
      },
      { rootMargin: '-80px 0px -55% 0px' },
    );
    for (const id of key.split(',')) {
      const node = document.getElementById(id);
      if (node) observer.observe(node);
    }
    return () => observer.disconnect();
  }, [key]);
  return active;
}

function SectionNav({ sections }: { sections: Section[] }) {
  const active = useActiveSection(sections.map((s) => s.id)) ?? sections[0]?.id;
  return (
    <nav aria-label="Settings sections" className="min-w-0 lg:sticky lg:top-10 lg:self-start">
      <ul className="-mx-4 flex gap-1 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0 lg:flex-col lg:gap-0.5 lg:overflow-visible">
        {sections.map((s) => (
          <li key={s.id} className="shrink-0">
            <a
              href={`#${s.id}`}
              aria-current={active === s.id ? 'location' : undefined}
              className={cx(
                'flex h-8 items-center rounded-md px-2.5 text-sm whitespace-nowrap transition-colors',
                active === s.id ? 'bg-panel-2 font-medium text-fg' : 'text-muted hover:bg-panel-2/60 hover:text-fg',
              )}
            >
              {s.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function SettingsSection({ id, children }: { id: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20 md:scroll-mt-8">
      {children}
    </section>
  );
}

function Pending({ error, loading }: { error: unknown; loading: boolean }) {
  if (error) {
    return (
      <div className="p-4">
        <ErrorNote error={error} />
      </div>
    );
  }
  return loading ? <SkeletonRows rows={3} /> : null;
}

function GeneralSection({ org }: { org: Organization }) {
  const detail = useOrganization(org.id);
  return (
    <Card>
      <CardHeader title="General" hint="How the organization is described and how members earn message points." />
      {detail.data ? <GeneralForm key={org.id} org={detail.data} /> : <Pending error={detail.error} loading={detail.isLoading} />}
    </Card>
  );
}

function BrandingSection({ org, prefix }: { org: Organization; prefix: string }) {
  const branding = useBranding(prefix);
  return (
    <Card>
      <CardHeader title="Branding" hint="The logo, website and accent color officers see in this dashboard." />
      {branding.data ? (
        <BrandingForm key={JSON.stringify(branding.data)} prefix={prefix} name={org.name} saved={branding.data} />
      ) : (
        <Pending error={branding.error} loading={branding.isLoading} />
      )}
    </Card>
  );
}

function ModulesSection({ org, modules }: { org: Organization; modules: ReturnType<typeof useModules> }) {
  const client = useQueryClient();
  const toggle = useMutation({
    mutationFn: (m: ModuleState) => send(`/api/organizations/${org.id}/modules`, 'PUT', { modules: { [m.name]: !m.enabled } }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['modules', org.id] });
      client.invalidateQueries({ queryKey: ['overview'] });
    },
  });
  return (
    <Card>
      <CardHeader title="Modules" hint="A module that is off returns 404 for this organization." />
      <Pending error={modules.error} loading={modules.isLoading} />
      {modules.data?.modules.map((m) => (
        <Row key={m.name}>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium">{m.name}</div>
            <div className="mt-0.5 text-xs text-muted">{m.description}</div>
          </div>
          <Switch checked={m.enabled} onChange={() => toggle.mutate(m)} disabled={toggle.isPending} label={m.name} />
        </Row>
      ))}
      {toggle.error ? (
        <div className="p-4">
          <ErrorNote error={toggle.error} />
        </div>
      ) : null}
    </Card>
  );
}

function CalendarSection({ orgId }: { orgId: number }) {
  const calendar = useQuery({
    queryKey: ['calendar-settings', orgId],
    queryFn: () => api<CalendarSettings>(`/api/organizations/${orgId}/calendar`),
  });
  const last = calendar.data?.last_sync_at;
  return (
    <Card>
      <CardHeader
        title="Calendar"
        hint="Where events come from in Notion and which Google calendar they go to."
        action={calendar.data ? <Badge tone={last ? 'ok' : 'muted'}>{last ? `Synced ${timeAgo(last)}` : 'Never synced'}</Badge> : null}
      />
      {calendar.data ? (
        <CalendarForm key={orgId} orgId={orgId} saved={calendar.data} />
      ) : (
        <Pending error={calendar.error} loading={calendar.isLoading} />
      )}
    </Card>
  );
}

function LeetCodeSection({ orgId }: { orgId: number }) {
  const leetcode = useQuery({
    queryKey: ['leetcode-settings', orgId],
    queryFn: () => api<{ settings: LeetCodeSettings; enabled: boolean }>(`/api/organizations/${orgId}/leetcode`),
  });
  return (
    <Card>
      <CardHeader title="LeetCode" hint="The daily problem post in the organization's Discord server." />
      {leetcode.data ? (
        <LeetCodeForm key={orgId} orgId={orgId} saved={leetcode.data.settings} />
      ) : (
        <Pending error={leetcode.error} loading={leetcode.isLoading} />
      )}
    </Card>
  );
}

function SecretsSection({ orgId }: { orgId: number }) {
  const secrets = useQuery({
    queryKey: ['secrets', orgId],
    queryFn: () => api<{ configured: boolean; secrets: SecretState[] }>(`/api/organizations/${orgId}/secrets`),
  });
  return (
    <Card>
      <CardHeader title="Secrets" hint="Encrypted with the server's SECRETS_KEY. Values are never shown." />
      {secrets.data && !secrets.data.configured ? (
        <div className="p-4">
          <ErrorNote error="SECRETS_KEY is not set on the server, so secrets cannot be saved." />
        </div>
      ) : null}
      <Pending error={secrets.error} loading={secrets.isLoading} />
      {secrets.data?.secrets.map((s) => <SecretRow key={s.name} orgId={orgId} secret={s} />)}
    </Card>
  );
}

export function SettingsPage() {
  const { org, prefix } = useCurrentOrg();
  const modules = useModules(org?.id);
  if (!org) return <PageSkeleton />;
  const on = (name: string) => Boolean(modules.data?.modules.find((m) => m.name === name)?.enabled);
  const sections: (Section & { body: ReactNode })[] = [
    { id: 'general', label: 'General', body: <GeneralSection org={org} /> },
    { id: 'branding', label: 'Branding', body: <BrandingSection org={org} prefix={prefix} /> },
    { id: 'modules', label: 'Modules', body: <ModulesSection org={org} modules={modules} /> },
    ...(on('calendar') ? [{ id: 'calendar', label: 'Calendar', body: <CalendarSection orgId={org.id} /> }] : []),
    ...(on('leetcode') ? [{ id: 'leetcode', label: 'LeetCode', body: <LeetCodeSection orgId={org.id} /> }] : []),
    { id: 'secrets', label: 'Secrets', body: <SecretsSection orgId={org.id} /> },
  ];
  return (
    <>
      <PageHeader title="Settings" description="General settings, branding, modules and secrets for this organization." />
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[160px_minmax(0,1fr)] lg:gap-10">
        <SectionNav sections={sections} />
        <div className="min-w-0 space-y-6">
          {sections.map((s) => (
            <SettingsSection key={s.id} id={s.id}>
              {s.body}
            </SettingsSection>
          ))}
        </div>
      </div>
    </>
  );
}
