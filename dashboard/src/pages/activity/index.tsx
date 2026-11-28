import { TabBar, useTabParam } from '../../components/tabs';
import { PageHeader } from '../../components/ui';
import { useCurrentOrg } from '../../lib/org';
import { useNotifications } from '../../lib/queries';
import { KnowledgeRuns } from '../knowledge/runs';
import { AuditLog } from './audit-log';
import { CiRuns } from './ci-runs';
import { ErrorsTab } from './errors';
import { NotificationsTab } from './notifications';
import { Timeline } from './timeline';

const TABS = [
  { id: 'timeline', label: 'Timeline' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'errors', label: 'Errors' },
  { id: 'changes', label: 'Changes' },
  { id: 'knowledge', label: 'Knowledge runs' },
  { id: 'ci', label: 'CI runs' },
] as const;

export function ActivityPage() {
  const { prefix } = useCurrentOrg();
  const open = useNotifications(prefix).data?.open ?? 0;
  const [tab, setTab] = useTabParam(TABS);
  return (
    <>
      <PageHeader />
      <TabBar
        label="Activity"
        tabs={TABS}
        value={tab}
        onChange={setTab}
        extra={(id) => (id === 'notifications' && open ? <span className="ml-1.5 text-xs text-muted tabular-nums">{open}</span> : null)}
      />
      {tab === 'errors' ? (
        <ErrorsTab />
      ) : tab === 'ci' ? (
        <CiRuns />
      ) : tab === 'knowledge' ? (
        <KnowledgeRuns />
      ) : tab === 'changes' ? (
        <AuditLog />
      ) : tab === 'notifications' ? (
        <NotificationsTab />
      ) : (
        <Timeline />
      )}
    </>
  );
}
