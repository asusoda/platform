import { ModuleOff, useModuleOn } from '../../components/module-gate';
import { TabBar, useTabParam } from '../../components/tabs';
import { PageSkeleton } from '../../components/ui';
import { ServicesTab } from '../apps';
import { MemberPodsTab } from '../compute';

// Each tab and the module that must be on to show it.
const TABS = [
  { id: 'services', label: 'Services', module: 'runpod' },
  { id: 'pods', label: 'Member pods', module: 'compute' },
] as const;

// What the org runs on its hosting providers: services that the org deploys, and pods that members connect to.
export function HostingPage() {
  const runpod = useModuleOn('runpod');
  const compute = useModuleOn('compute');
  const on = { runpod: runpod.on, compute: compute.on };
  const shown = TABS.filter((t) => on[t.module]);
  const [tab, setTab] = useTabParam(shown.length ? shown : TABS);
  if (runpod.loading || compute.loading) return <PageSkeleton />;
  if (!shown.length) return <ModuleOff module="compute" title="Hosting" />;
  const tabs = <TabBar label="Hosting" tabs={shown} value={tab} onChange={setTab} />;
  return tab === 'pods' ? <MemberPodsTab tabs={tabs} /> : <ServicesTab tabs={tabs} />;
}
