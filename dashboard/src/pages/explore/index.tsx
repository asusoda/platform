import { useDeferredValue, useState } from 'react';
import { TabBar, useTabParam } from '../../components/tabs';
import { ErrorNote, PageError, PageHeader, PageSkeleton, SearchInput } from '../../components/ui';
import { useCurrentOrg } from '../../lib/org';
import { useModuleCatalog } from '../../lib/queries';
import type { CatalogModule } from '../../lib/types';
import { IntegrationsTab } from './integrations';
import { ModuleCard, ModuleGrid, RemoveModuleDialog, useModuleSwitch } from './modules';
import { SubmodulesTab } from './submodules';

const TABS = [
  { id: 'features', label: 'Features' },
  { id: 'shared', label: 'Shared' },
  { id: 'integrations', label: 'Integrations' },
] as const;

// The tab ids before the rename, from old links and notifications
const ALIASES = { modules: 'features', submodules: 'shared' } as const;

function ModulesTab({ query }: { query: string }) {
  const { org, prefix } = useCurrentOrg();
  const catalog = useModuleCatalog(prefix);
  const [removing, setRemoving] = useState<CatalogModule | null>(null);
  const change = useModuleSwitch(org?.id, prefix, () => setRemoving(null));

  if (catalog.isLoading || !org) return <PageSkeleton />;
  if (catalog.error || !catalog.data) return <PageError error={catalog.error ?? 'No data'} retry={() => void catalog.refetch()} />;

  return (
    <>
      {change.error ? (
        <div className="mb-4">
          <ErrorNote error={change.error} />
        </div>
      ) : null}
      <ModuleGrid
        categories={catalog.data.categories}
        modules={catalog.data.modules}
        query={query}
        render={(m) => (
          <ModuleCard
            key={m.name}
            m={m}
            prefix={prefix}
            busy={change.isPending}
            onAdd={() => change.mutate({ m, on: true })}
            onRemove={() => setRemoving(m)}
          />
        )}
      />
      <RemoveModuleDialog
        module={removing}
        busy={change.isPending}
        onClose={() => setRemoving(null)}
        onRemove={(m) => change.mutate({ m, on: false })}
      />
    </>
  );
}

function SubmodulesTabFor({ query }: { query: string }) {
  const { prefix } = useCurrentOrg();
  return <SubmodulesTab prefix={prefix} query={query} />;
}

// Everything an org can add: features (modules), shared content (submodules) it subscribes to, and services it connects.
export function ExplorePage() {
  const [tab, setTab] = useTabParam(TABS, ALIASES);
  const [query, setQuery] = useState('');
  const deferred = useDeferredValue(query);
  return (
    <>
      <PageHeader />
      <TabBar
        label="Explore"
        tabs={TABS}
        value={tab}
        onChange={setTab}
        action={
          <SearchInput
            className="w-full sm:w-64"
            placeholder={tab === 'features' ? 'Search features' : tab === 'shared' ? 'Search shared content' : 'Search integrations'}
            aria-label="Search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        }
      />
      {tab === 'features' ? (
        <ModulesTab query={deferred} />
      ) : tab === 'shared' ? (
        <SubmodulesTabFor query={deferred} />
      ) : (
        <IntegrationsTab query={deferred} />
      )}
    </>
  );
}
