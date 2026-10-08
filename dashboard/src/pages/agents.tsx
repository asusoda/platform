import { Card, CardHeader, Empty, ErrorNote, Loading, PageHeader, Row, Stat } from '../components/ui';
import { compact, timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import { useOverview } from '../lib/queries';

export function AgentsPage() {
  const { prefix } = useCurrentOrg();
  const { data, isLoading, error } = useOverview(prefix);
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorNote error={error ?? 'No data'} />;
  const a = data.sections.agents;
  const agents = data.sections.tokens.tokens.filter((t) => t.kind === 'agent');
  const linked = Object.entries(data.sections.accounts.linked);
  return (
    <>
      <PageHeader
        title="Agents"
        description="Counts only. Conversations and memories belong to the member; officers cannot read them."
      />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Conversations this week" value={compact(a.active_7_days)} sub={`${compact(a.conversations)} kept`} />
        <Stat label="Members this week" value={compact(a.members_7_days)} />
        <Stat label="Memories" value={compact(a.memories)} />
        <Stat label="Waiting for confirmation" value={a.pending_actions} />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Agent tokens" hint="Agents call the platform with these" />
          {agents.length ? (
            agents.map((t) => (
              <Row key={t.name}>
                <span className="flex-1 text-sm">{t.name}</span>
                <span className="hidden truncate font-mono text-xs text-muted sm:block">{t.scopes.join(' ')}</span>
                <span className="text-xs text-muted">used {timeAgo(t.last_used_at)}</span>
              </Row>
            ))
          ) : (
            <Empty>No agent tokens. Create one under Tokens.</Empty>
          )}
        </Card>
        <Card>
          <CardHeader title="Linked accounts" hint="Members who connected an account for agents to use" />
          {linked.length ? (
            linked.map(([provider, count]) => (
              <Row key={provider}>
                <span className="flex-1 text-sm capitalize">{provider}</span>
                <span className="text-sm tabular-nums">{count}</span>
              </Row>
            ))
          ) : (
            <Empty>No linked accounts.</Empty>
          )}
        </Card>
      </div>
    </>
  );
}
