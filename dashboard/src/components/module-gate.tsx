import { PowerOff } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { useCurrentOrg } from '../lib/org';
import { useModules } from '../lib/queries';
import { Card, EmptyState, PageHeader, PageSkeleton } from './ui';

// Whether an optional module is on for the current org. True until the states load or when they cannot be read.
export function useModuleOn(name: string): { on: boolean; loading: boolean } {
  const { org } = useCurrentOrg();
  const modules = useModules(org?.id);
  const state = modules.data?.modules.find((m) => m.name === name);
  return { on: state ? state.enabled : true, loading: !org || modules.isLoading };
}

// The page of an optional module, or a note that the module is off with a link to the Modules page.
export function ModuleGate({ module, title, children }: { module: string; title: string; children: ReactNode }) {
  const { on, loading } = useModuleOn(module);
  if (loading) return <PageSkeleton />;
  if (on) return children;
  return <ModuleOff module={module} title={title} />;
}

// A page header and a note that the module is off, with a link to the Modules page.
export function ModuleOff({ module, title }: { module: string; title: string }) {
  const { prefix } = useCurrentOrg();
  return (
    <>
      <PageHeader title={title} />
      <Card>
        <EmptyState
          icon={PowerOff}
          title={`The ${module} module is off`}
          action={
            <Link
              to={`/${prefix}/modules`}
              className="inline-flex h-8 items-center rounded-md bg-accent px-3 text-sm font-medium text-accent-fg shadow-xs hover:opacity-85"
            >
              Open Modules
            </Link>
          }
        >
          Add the module to the org on the Modules page to use this page. While it is off, its routes return 404 for this
          org.
        </EmptyState>
      </Card>
    </>
  );
}
