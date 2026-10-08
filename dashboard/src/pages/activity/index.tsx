import { TabBar, useTabParam } from '../../components/tabs';
import { PageHeader } from '../../components/ui';
import { KnowledgeRuns } from '../knowledge/runs';
import { AuditLog } from './audit-log';
import { CiRuns } from './ci-runs';

const TABS = [
  { id: 'changes', label: 'Changes' },
  { id: 'knowledge', label: 'Knowledge runs' },
  { id: 'ci', label: 'CI runs' },
] as const;

export function ActivityPage() {
  const [tab, setTab] = useTabParam(TABS);
  return (
    <>
      <PageHeader
        title="Activity"
        description="Every change an officer, token or job made in this organization, its crawls and uploads, and the CI runs of its repositories."
      />
      <TabBar label="Activity" tabs={TABS} value={tab} onChange={setTab} />
      {tab === 'ci' ? <CiRuns /> : tab === 'knowledge' ? <KnowledgeRuns /> : <AuditLog />}
    </>
  );
}
