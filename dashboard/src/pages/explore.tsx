import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowUpRight, Plus, SearchX } from 'lucide-react';
import { useDeferredValue, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { TabBar } from '../components/tabs';
import { Button, Card, Dialog, EmptyState, ErrorNote, FormActions, PageHeader, PageSkeleton, SearchInput, Spinner } from '../components/ui';
import { send } from '../lib/api';
import { matches } from '../lib/modules';
import { useCurrentOrg } from '../lib/org';
import { useModuleCatalog } from '../lib/queries';
import type { CatalogModule } from '../lib/types';

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
  uptime: 'uptime',
};

const ALL = 'all';

// One module: title, one line of what it does, what is missing, and one action.
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
  const missing = m.needs.filter((n) => !n.connected && !n.optional);
  return (
    <Card className="flex min-h-36 flex-col p-4" data-module={m.name}>
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold">{m.title}</h3>
        {m.enabled && page ? (
          <Link to={`/${prefix}/${page}`} aria-label={`Open ${m.title}`} className="text-muted transition-colors hover:text-fg">
            <ArrowUpRight className="size-4" />
          </Link>
        ) : null}
      </div>
      <p className="mt-1 line-clamp-2 text-sm text-pretty text-muted">{m.description}</p>
      <div className="mt-auto flex items-center justify-between gap-3 pt-4">
        {missing.length ? (
          <Link to={`/${prefix}/integrations`} className="truncate text-xs text-warn hover:underline">
            Needs {missing.map((n) => n.label).join(', ')}
          </Link>
        ) : (
          <span className="text-xs text-muted">{m.category}</span>
        )}
        {!m.switchable ? (
          <span className="shrink-0 text-xs text-muted">Included</span>
        ) : m.enabled ? (
          <Button variant="ghost" className="h-7 shrink-0 px-2 text-xs" disabled={busy} onClick={onRemove}>
            Remove
          </Button>
        ) : (
          <Button className="h-7 shrink-0 px-2 text-xs" disabled={busy || !m.ready} onClick={onAdd}>
            <Plus className="size-3.5" /> Add
          </Button>
        )}
      </div>
    </Card>
  );
}

// Every module an org can use, to search and add.
export function ExplorePage() {
  const { org, prefix } = useCurrentOrg();
  const client = useQueryClient();
  const catalog = useModuleCatalog(prefix);
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState('');
  const deferred = useDeferredValue(query);
  const [removing, setRemoving] = useState<CatalogModule | null>(null);
  const change = useMutation({
    mutationFn: ({ m, on }: { m: CatalogModule; on: boolean }) =>
      send(`/api/organizations/${org?.id}/modules`, 'PUT', { modules: { [m.name]: on } }),
    onSuccess: () => {
      setRemoving(null);
      client.invalidateQueries({ queryKey: ['catalog', prefix] });
      client.invalidateQueries({ queryKey: ['modules', org?.id] });
      client.invalidateQueries({ queryKey: ['overview'] });
    },
  });

  if (catalog.isLoading || !org) return <PageSkeleton />;
  if (catalog.error || !catalog.data) return <ErrorNote error={catalog.error ?? 'No data'} />;

  const { categories, modules } = catalog.data;
  const tabs = [{ id: ALL, label: 'All' }, ...categories.map((c) => ({ id: c, label: c }))];
  const category = tabs.some((t) => t.id === params.get('category')) ? (params.get('category') as string) : ALL;
  const setCategory = (id: string) => setParams(id === ALL ? {} : { category: id }, { replace: true });
  const shown = modules.filter((m) => (category === ALL || m.category === category) && matches(m, deferred));

  return (
    <>
      <PageHeader title="Explore" description="Find modules for your org. Remove keeps a module's data." />
      <SearchInput
        className="mb-2 w-full sm:w-80"
        placeholder="Search modules"
        aria-label="Search modules"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <TabBar label="Category" tabs={tabs} value={category} onChange={setCategory} />
      {change.error ? (
        <div className="mb-4">
          <ErrorNote error={change.error} />
        </div>
      ) : null}
      {shown.length ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {shown.map((m) => (
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
      ) : (
        <Card>
          <EmptyState icon={SearchX} title="No module matches">
            Change the search text or select All.
          </EmptyState>
        </Card>
      )}
      <Dialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        title={`Remove ${removing?.title ?? ''}?`}
        description="Its pages leave the sidebar. Its data stays, and comes back when you add it again."
      >
        <FormActions>
          <Button variant="danger" disabled={change.isPending} onClick={() => removing && change.mutate({ m: removing, on: false })}>
            {change.isPending ? <Spinner className="size-3.5" /> : null} Remove
          </Button>
          <Button variant="ghost" onClick={() => setRemoving(null)}>
            Cancel
          </Button>
        </FormActions>
      </Dialog>
    </>
  );
}
