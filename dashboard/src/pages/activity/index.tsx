import { TabBar, useTabParam } from '../../components/tabs';
import { PageHeader } from '../../components/ui';
import { KnowledgeRuns } from '../knowledge/runs';
import { AuditLog } from './audit-log';
import { CiRuns } from './ci-runs';
import { ErrorsTab } from './errors';

const TABS = [
  { id: 'changes', label: 'Changes' },
  { id: 'knowledge', label: 'Knowledge runs' },
  { id: 'ci', label: 'CI runs' },
  { id: 'errors', label: 'Errors' },
] as const;

export function ActivityPage() {
  const [tab, setTab] = useTabParam(TABS);
  return (
    <>
      <PageHeader
        title="Activity"
        description="Changes by officers, tokens and jobs, knowledge runs, CI runs of the org's repos, and errors."
      />
      <TabBar label="Activity" tabs={TABS} value={tab} onChange={setTab} />
      {tab === 'errors' ? <ErrorsTab /> : tab === 'ci' ? <CiRuns /> : tab === 'knowledge' ? <KnowledgeRuns /> : <AuditLog />}
    </>
  );
}
