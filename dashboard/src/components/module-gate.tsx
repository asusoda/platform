import { PowerOff } from 'lucide-react';
import type { ReactNode } from 'react';
import { useCurrentOrg } from '../lib/org';
import { useModules } from '../lib/queries';
import { Card, EmptyState, LinkButton, PageHeader, PageSkeleton } from './ui';

// Whether an optional module is on for the current org. True until the states load or when they cannot be read.
export function useModuleOn(name: string): { on: boolean; loading: boolean } {
  const { org } = useCurrentOrg();
  const modules = useModules(org?.id);
  const state = modules.data?.modules.find((m) => m.name === name);
  return { on: state ? state.enabled : true, loading: !org || modules.isLoading };
}

// The page of an optional module, or a note that the module is off with a link to Explore.
export function ModuleGate({ module, title, children }: { module: string; title: string; children: ReactNode }) {
  const { on, loading } = useModuleOn(module);
  if (loading) return <PageSkeleton />;
  if (on) return children;
  return <ModuleOff title={title} />;
}

// A page header and a note that the module is off, with a link to Explore.
export function ModuleOff({ title }: { title: string }) {
  const { prefix } = useCurrentOrg();
  return (
    <>
      <PageHeader title={title} />
      <Card>
        <EmptyState
          icon={PowerOff}
          title={`${title} is off`}
          action={
            <LinkButton variant="primary" to={`/${prefix}/explore`}>
              Open Explore
            </LinkButton>
          }
        >
          Add it on Explore.
        </EmptyState>
      </Card>
    </>
  );
}
