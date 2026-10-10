import { IntegrationHint } from '../../components/integration-hint';
import { useQuery } from '@tanstack/react-query';
import { Boxes, Plus } from 'lucide-react';
import { type ReactNode, useState } from 'react';
import { Button, Card, CardHeader, Dialog, EmptyState, ErrorNote, Mono, Notice, PageHeader, SkeletonRows } from '../../components/ui';
import { api } from '../../lib/api';
import { useCurrentOrg } from '../../lib/org';
import type { App, AppKind } from '../../lib/types';
import { AppPanel } from './detail';
import { RegisterApp } from './register';
import { providerTitle, useProviders } from '../hosting/providers';
import { AppTable } from './table';

// Apps are grouped by what they are for; the host is a detail of each app.
const KINDS: { kind: AppKind; title: string; hint: string }[] = [
  { kind: 'bot', title: 'Bots', hint: 'Discord and chat bots' },
  { kind: 'agent', title: 'Agents', hint: 'AI agents that call the platform with a token' },
  { kind: 'site', title: 'Sites', hint: 'Websites and web apps' },
  { kind: 'service', title: 'Services', hint: 'APIs, workers and anything else' },
];

// The Services tab of the Hosting page. tabs is the tab bar, shown under the page header.
export function ServicesTab({ tabs }: { tabs: ReactNode }) {
  const { prefix } = useCurrentOrg();
  const [registering, setRegistering] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [notice, setNotice] = useState<ReactNode>(null);
  const list = useQuery({
    queryKey: ['apps', prefix],
    queryFn: () => api<{ apps: App[] }>(`/api/dashboard/${prefix}/apps`),
    enabled: Boolean(prefix),
    refetchInterval: (q) => (q.state.data?.apps.some((a) => a.latest_deployment?.status === 'deploying') ? 10_000 : false),
  });
  const apps = list.data?.apps ?? [];
  const providers = useProviders(prefix);
  const register = (
    <Button variant="primary" onClick={() => setRegistering(true)}>
      <Plus className="size-4" /> Register app
    </Button>
  );
  const current = apps.find((a) => a.name === open);
  return (
    <>
      <PageHeader
        title="Hosting"
        description="The org's bots, agents, sites and services on its hosting providers. Register a manifest, then deploy image tags here or from CI."
        action={register}
      />
      {tabs}
      {providers.data?.some((p) => p.configured) ? null : <IntegrationHint keys={providers.data?.map((p) => p.integration) ?? ['runpod']} />}
      {notice ? <Notice onDismiss={() => setNotice(null)}>{notice}</Notice> : null}
      {list.error ? (
        <div className="mb-4">
          <ErrorNote error={list.error} />
        </div>
      ) : null}
      {list.isLoading ? (
        <Card>
          <SkeletonRows />
        </Card>
      ) : apps.length ? (
        <div className="grid gap-6">
          {KINDS.filter((k) => apps.some((a) => a.kind === k.kind)).map((k) => {
            const group = apps.filter((a) => a.kind === k.kind);
            return (
              <Card key={k.kind}>
                <CardHeader title={k.title} hint={`${k.hint} · ${group.length} ${group.length === 1 ? 'app' : 'apps'}`} />
                <AppTable apps={group} providers={providers.data} onOpen={setOpen} />
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <EmptyState icon={Boxes} title="No apps" action={register}>
            Register a bot, agent, site or service with its manifest: what it is, the image, the GPU or CPU, ports, env and a health path.
          </EmptyState>
        </Card>
      )}

      <Dialog
        open={registering}
        onClose={() => setRegistering(false)}
        title="Register app"
        description="Deploys use the provider account on Integrations. Set any app_ secrets in Settings first."
        wide
      >
        <RegisterApp
          prefix={prefix}
          onDone={(name) => {
            setRegistering(false);
            if (name) setOpen(name);
          }}
        />
      </Dialog>

      <Dialog
        open={open !== null}
        onClose={() => setOpen(null)}
        title={open ?? ''}
        description={current ? (current.repo ? `From ${current.repo}` : 'Inline manifest') : undefined}
        wide
      >
        {open ? (
          <AppPanel
            key={open}
            prefix={prefix}
            name={open}
            onDeleted={(name, podId) => {
              setOpen(null);
              setNotice(
                podId ? (
                  <>
                    Deleted {name}. The pod <Mono className="text-fg">{podId}</Mono> still runs and bills; terminate it on {providerTitle(providers.data, current?.provider)}.
                  </>
                ) : (
                  `Deleted ${name}.`
                ),
              );
            }}
          />
        ) : null}
      </Dialog>
    </>
  );
}
