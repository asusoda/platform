import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Blocks, Check, Package, Plus, SearchX } from 'lucide-react';
import { useDeferredValue, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { TabBar } from '../components/tabs';
import {
  Badge,
  Button,
  Card,
  Dialog,
  Dot,
  EmptyState,
  ErrorNote,
  FormActions,
  Notice,
  PageHeader,
  PageSkeleton,
  quietLink,
  SearchInput,
  Stat,
  StatGrid,
} from '../components/ui';
import { send } from '../lib/api';
import { useCurrentOrg } from '../lib/org';
import { matches } from '../lib/modules';
import { useModuleCatalog } from '../lib/queries';
import type { CatalogModule, ModuleNeed } from '../lib/types';

// The dashboard page of each module that has one.
const MODULE_PAGES: Record<string, string> = {
  points: 'points',
  storefront: 'store',
  calendar: 'calendar',
  leetcode: 'leetcode',
  compute: 'hosting?tab=pods',
  runpod: 'hosting',
  alerts: 'alerts',
  knowledge: 'knowledge',
  packs: 'knowledge',
  mcp: 'mcp',
  agents: 'mcp',
};

const ALL = 'all';

function StateBadge({ m }: { m: CatalogModule }) {
  if (!m.switchable) return <Badge tone="muted">Always on</Badge>;
  return m.enabled ? <Badge tone="ok">On</Badge> : <Badge tone="muted">Off</Badge>;
}

function NeedLine({ need, prefix }: { need: ModuleNeed; prefix: string }) {
  const tone = need.connected ? 'ok' : need.optional ? 'muted' : 'warn';
  const what = need.optional ? `Works better with ${need.label}` : `Needs ${need.label}`;
  return (
    <li className="flex items-start gap-2 text-xs">
      <span className="mt-1">
        <Dot tone={tone} />
      </span>
      <span className="min-w-0 text-pretty">
        <span className={need.connected || need.optional ? 'text-muted' : 'text-fg'}>{what}</span>
        {need.connected ? (
          <span className="text-muted">. Connected.</span>
        ) : need.kind === 'setting' ? (
          <span className="text-muted">. Not set in .env on the server.</span>
        ) : (
          <>
            <span className="text-muted">. Not connected. </span>
            <Link to={`/${prefix}/integrations`} className="font-medium text-fg underline underline-offset-2">
              Open Integrations
            </Link>
          </>
        )}
      </span>
    </li>
  );
}

function ModuleCard({
  m,
  prefix,
  busy,
  onAdd,
  onRemove,
}: {
  m: CatalogModule;
  prefix: string;
  busy: boolean;
  onAdd: () => void;
  onRemove: () => void;
}) {
  const page = MODULE_PAGES[m.name];
  const blocked = m.switchable && !m.enabled && !m.ready;
  return (
    <Card className="flex flex-col" data-module={m.name}>
      <div className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">{m.title}</h3>
          <StateBadge m={m} />
        </div>
        <p className="mt-1 text-sm text-pretty text-muted">{m.description}</p>
        {m.needs.length ? (
          <ul className="mt-3 space-y-1.5" aria-label={`What ${m.title} needs`}>
            {m.needs.map((n) => (
              <NeedLine key={n.key} need={n} prefix={prefix} />
            ))}
          </ul>
        ) : null}
        {m.packs.length ? (
          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-muted">
            <Package className="size-3.5" aria-hidden /> Packs
            {m.packs.map((p) => (
              <span key={p.name} title={p.description} className="rounded-md border border-line px-1.5 py-0.5 text-fg">
                {p.title}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-line px-4 py-3">
        {!m.switchable ? (
          <span className="text-xs text-muted">Always on for every org</span>
        ) : m.enabled ? (
          <Button variant="secondary" disabled={busy} onClick={onRemove}>
            Remove
          </Button>
        ) : (
          <Button variant="primary" disabled={busy || blocked} onClick={onAdd} title={blocked ? 'Connect what the module needs first' : undefined}>
            <Plus className="size-4" /> Add to organization
          </Button>
        )}
        {m.enabled && page ? (
          <Link to={`/${prefix}/${page}`} className={`${quietLink} ml-auto`}>
            Open
          </Link>
        ) : null}
      </div>
    </Card>
  );
}

// Every module that an org can add or remove, by category, with what each one needs and the packs it uses.
export function ModulesPage() {
  const { org, prefix } = useCurrentOrg();
  const client = useQueryClient();
  const catalog = useModuleCatalog(prefix);
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState('');
  const deferred = useDeferredValue(query);
  const [removing, setRemoving] = useState<CatalogModule | null>(null);
  const [notice, setNotice] = useState<{ m: CatalogModule; on: boolean } | null>(null);
  const change = useMutation({
    mutationFn: ({ m, on }: { m: CatalogModule; on: boolean }) =>
      send(`/api/organizations/${org?.id}/modules`, 'PUT', { modules: { [m.name]: on } }),
    onSuccess: (_, vars) => {
      setRemoving(null);
      setNotice(vars);
      client.invalidateQueries({ queryKey: ['catalog', prefix] });
      client.invalidateQueries({ queryKey: ['modules', org?.id] });
      client.invalidateQueries({ queryKey: ['overview'] });
    },
  });

  if (catalog.isLoading || !org) return <PageSkeleton stats />;
  if (catalog.error || !catalog.data) return <ErrorNote error={catalog.error ?? 'No data'} />;

  const { categories, modules } = catalog.data;
  const tabs = [{ id: ALL, label: 'All' }, ...categories.map((c) => ({ id: c, label: c }))];
  const category = tabs.some((t) => t.id === params.get('category')) ? (params.get('category') as string) : ALL;
  const setCategory = (id: string) => setParams(id === ALL ? {} : { category: id }, { replace: true });
  const shown = modules.filter((m) => (category === ALL || m.category === category) && matches(m, deferred));
  const switchable = modules.filter((m) => m.switchable);
  const on = switchable.filter((m) => m.enabled).length;
  const needSetup = modules.filter((m) => !m.ready).length;

  return (
    <>
      <PageHeader
        title="Modules"
        description="Add the modules your org uses. Remove turns a module off for this org and keeps its data. Core modules, such as sign-in and the member list, are always on."
      />
      {notice ? (
        <Notice onDismiss={() => setNotice(null)}>
          {notice.on ? (
            <>
              {notice.m.title} is on.{' '}
              {MODULE_PAGES[notice.m.name] ? (
                <Link to={`/${prefix}/${MODULE_PAGES[notice.m.name]}`} className="font-medium underline underline-offset-2">
                  Open {notice.m.title}
                </Link>
              ) : null}
            </>
          ) : (
            `${notice.m.title} is off. Its data stays, and you can add it again at any time.`
          )}
        </Notice>
      ) : null}
      <StatGrid className="mb-6">
        <Stat label="On" value={on} sub={`of ${switchable.length} that you can add`} icon={<Check className="size-3.5" />} />
        <Stat label="Off" value={switchable.length - on} sub="Add them below" />
        <Stat label="Always on" value={modules.length - switchable.length} sub="Not switched per org" icon={<Blocks className="size-3.5" />} />
        <Stat label="Needs setup" value={needSetup} sub="Not connected yet" />
      </StatGrid>
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <SearchInput
          className="w-full sm:w-72"
          placeholder="Search modules"
          aria-label="Search modules"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <TabBar label="Category" tabs={tabs} value={category} onChange={setCategory} />
      {change.error ? (
        <div className="mb-4">
          <ErrorNote error={change.error} />
        </div>
      ) : null}
      {shown.length === 0 ? (
        <Card>
          <EmptyState icon={SearchX} title="No module matches">
            Change the search text or select All.
          </EmptyState>
        </Card>
      ) : (
        <div className="space-y-8">
          {categories.map((c) => {
            const items = shown.filter((m) => m.category === c);
            return items.length ? (
              <section key={c} aria-label={c}>
                <h2 className="mb-3 text-sm font-semibold">{c}</h2>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {items.map((m) => (
                    <ModuleCard
                      key={m.name}
                      m={m}
                      prefix={prefix}
                      busy={change.isPending}
                      onAdd={() => change.mutate({ m, on: true })}
                      onRemove={() => setRemoving(m)}
                    />
                  ))}
                </div>
              </section>
            ) : null;
          })}
        </div>
      )}
      <Dialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        title={`Remove ${removing?.title ?? ''}?`}
        description="The module turns off for this org. Its pages leave the sidebar and its routes return 404."
      >
        <p className="text-sm text-pretty text-muted">
          Its data stays in the database. If you add the module again, it has the same data.
        </p>
        <div className="mt-4">
          <FormActions>
            <Button variant="danger" disabled={change.isPending} onClick={() => removing && change.mutate({ m: removing, on: false })}>
              Remove
            </Button>
            <Button variant="ghost" onClick={() => setRemoving(null)}>
              Cancel
            </Button>
          </FormActions>
        </div>
      </Dialog>
    </>
  );
}
