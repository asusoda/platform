import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, SearchX } from 'lucide-react';
import { type ReactNode, useState } from 'react';
import { Link, useParams } from 'react-router';
import { LimitTable } from '../../components/limits';
import { NotificationItem } from '../../components/notifications';
import {
  BackLink,
  Badge,
  Card,
  CardHeader,
  DocsLink,
  EmptyState,
  ErrorNote,
  LinkButton,
  PageError,
  PageHeader,
  PageSkeleton,
  quietLink,
  Row,
  Switch,
} from '../../components/ui';
import { api } from '../../lib/api';
import { byUse } from '../../lib/limits';
import { MODULE_PAGES, moduleDocs, moduleIcon, notificationModule } from '../../lib/modules';
import { useCurrentOrg } from '../../lib/org';
import { useModuleCatalog, useNotifications } from '../../lib/queries';
import type { CatalogModule, LimitRow, ToolGroups } from '../../lib/types';
import { RemoveModuleDialog, SubModules, SubmoduleSwitches, useModuleSwitch } from './modules';

// How many recent notifications of the module the page shows.
const RECENT = 5;

function Section({ title, hint, action, children }: { title: string; hint?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <Card>
      <CardHeader title={title} hint={hint} action={action} />
      {children}
    </Card>
  );
}

// What the module needs: each integration or setting, and whether the org has it.
function Needs({ m, prefix }: { m: CatalogModule; prefix: string }) {
  if (!m.needs.length) return null;
  return (
    <Section title="Needs">
      {m.needs.map((n) => (
        <Row key={n.key}>
          <span className="min-w-0 flex-1 truncate text-sm">{n.label}</span>
          {n.optional ? <Badge>Optional</Badge> : null}
          {n.connected ? (
            <Badge tone="ok">Set</Badge>
          ) : n.kind === 'integration' ? (
            <LinkButton size="sm" to={`/${prefix}/explore?tab=integrations`}>
              Connect
            </LinkButton>
          ) : (
            <DocsLink page={moduleDocs(m.name)} className="h-7" />
          )}
        </Row>
      ))}
    </Section>
  );
}

// The sub-modules of the module, with their switches, and its shared content. Knowledge and feeds list what the
// org can subscribe to or add.
function Submodules({ m, prefix, busy, onSwitch }: { m: CatalogModule; prefix: string; busy: boolean; onSwitch: (key: string, on: boolean) => void }) {
  const live = m.enabled && (m.name === 'knowledge' || m.name === 'feeds');
  if (!live && !m.submodules.length && !m.shared_content.length) return null;
  return (
    <Section title="Sub-modules">
      <div className="-mt-px">
        <SubmoduleSwitches m={m} busy={busy} onSwitch={onSwitch} />
      </div>
      {live ? (
        <div className="-mt-px">
          <SubModules m={m} prefix={prefix} />
        </div>
      ) : (
        m.shared_content.map((s) => (
          <Row key={s.name}>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{s.title}</div>
              <div className="truncate text-xs text-muted">{s.description}</div>
            </div>
          </Row>
        ))
      )}
    </Section>
  );
}

// The org's use of each limit of the module.
function Limits({ m, orgId, prefix }: { m: CatalogModule; orgId: number; prefix: string }) {
  const limits = useQuery({
    queryKey: ['limits', orgId],
    queryFn: () => api<{ limits: LimitRow[] }>(`/api/organizations/${orgId}/limits`),
    enabled: m.limits.length > 0,
  });
  if (!m.limits.length) return null;
  const rows = byUse((limits.data?.limits ?? []).filter((r) => r.module === m.name));
  return (
    <Section
      title="Limits"
      action={
        <Link to={`/${prefix}/settings#limits`} className={quietLink}>
          All limits
        </Link>
      }
    >
      {limits.error ? (
        <div className="p-4">
          <ErrorNote error={limits.error} />
        </div>
      ) : rows.length ? (
        <LimitTable rows={rows} />
      ) : (
        m.limits.map((l) => (
          <Row key={l.key}>
            <span className="text-sm">{l.label}</span>
          </Row>
        ))
      )}
    </Section>
  );
}

// The tool group of the module and whether the org's tokens can call it.
function Tools({ m, prefix }: { m: CatalogModule; prefix: string }) {
  const groups = useQuery({
    queryKey: ['tool-groups', prefix],
    queryFn: () => api<ToolGroups>(`/api/dashboard/${prefix}/tool-groups`),
  });
  const group = groups.data?.groups.find((g) => g.layer === 'module' && g.key === m.name);
  if (!group) return null;
  const allowed = groups.data?.allowed === null || groups.data?.allowed?.includes(group.key);
  return (
    <Section title="Tools">
      <Row>
        <span className="min-w-0 flex-1 text-sm">
          {group.tools === null ? 'Tools' : `${group.tools} ${group.tools === 1 ? 'tool' : 'tools'}`} for agents and tokens
        </span>
        <Badge tone={allowed ? 'ok' : 'muted'}>{allowed ? 'Allowed' : 'Not allowed'}</Badge>
        <Link to={`/${prefix}/connections`} className={quietLink}>
          Tool groups
        </Link>
      </Row>
    </Section>
  );
}

// The newest notifications of the module, with a link to Activity.
function Recent({ m, prefix }: { m: CatalogModule; prefix: string }) {
  const notes = useNotifications(prefix);
  const mine = (notes.data?.notifications ?? []).filter((n) => notificationModule(n.module) === m.name).slice(0, RECENT);
  if (!mine.length) return null;
  return (
    <Section
      title="Recent activity"
      action={
        <Link to={`/${prefix}/activity`} className={quietLink}>
          All activity
        </Link>
      }
    >
      <ul className="divide-y divide-line">
        {mine.map((n) => (
          <NotificationItem key={n.id} n={n} compact />
        ))}
      </ul>
    </Section>
  );
}

// One module of the org: its switch, what it needs, its sub-modules, limits, tools and recent activity.
export function ModulePage() {
  const { module: name = '' } = useParams();
  const { org, prefix } = useCurrentOrg();
  const catalog = useModuleCatalog(prefix);
  const [removing, setRemoving] = useState<CatalogModule | null>(null);
  const change = useModuleSwitch(org?.id, prefix, () => setRemoving(null));
  const back = <BackLink to={`/${prefix}/explore`}>Explore</BackLink>;

  if (catalog.isLoading || !org) return <PageSkeleton />;
  if (catalog.error || !catalog.data) {
    return (
      <>
        {back}
        <PageHeader title={name} />
        <PageError error={catalog.error ?? 'No data'} retry={() => void catalog.refetch()} />
      </>
    );
  }
  const m = [...catalog.data.modules, ...catalog.data.layers].find((x) => x.name === name);
  if (!m) {
    return (
      <>
        {back}
        <PageHeader title={name} />
        <Card>
          <EmptyState icon={SearchX} title="No such module" />
        </Card>
      </>
    );
  }

  const Icon = moduleIcon(m.name);
  const page = MODULE_PAGES[m.name];
  return (
    <>
      {back}
      <PageHeader
        title={
          <span className="flex items-center gap-2.5">
            <Icon className="size-5 text-muted" />
            {m.title}
          </span>
        }
        description={m.description}
        docs={moduleDocs(m.name)}
        action={
          <>
            {m.enabled && page ? (
              <LinkButton to={`/${prefix}/${page}`}>
                Open <ArrowUpRight className="size-4" />
              </LinkButton>
            ) : null}
            {m.switchable ? (
              <span className="flex h-8 items-center gap-2 text-sm text-muted">
                {m.enabled ? 'On' : 'Off'}
                <Switch
                  checked={m.enabled}
                  disabled={change.isPending || (!m.enabled && !m.ready)}
                  label={`${m.title} on`}
                  onChange={(on) => (on ? change.mutate({ m, on: true }) : setRemoving(m))}
                />
              </span>
            ) : (
              <Badge>Included</Badge>
            )}
          </>
        }
      />
      {change.error ? (
        <div className="mb-4">
          <ErrorNote error={change.error} />
        </div>
      ) : null}
      <div className="grid gap-6">
        <Needs m={m} prefix={prefix} />
        <Submodules m={m} prefix={prefix} busy={change.isPending} onSwitch={(key, on) => change.mutate({ m: { name: key }, on })} />
        {m.enabled ? (
          <>
            <Limits m={m} orgId={org.id} prefix={prefix} />
            <Tools m={m} prefix={prefix} />
            <Recent m={m} prefix={prefix} />
          </>
        ) : null}
      </div>
      <RemoveModuleDialog module={removing} busy={change.isPending} onClose={() => setRemoving(null)} onRemove={(x) => change.mutate({ m: x, on: false })} />
    </>
  );
}
