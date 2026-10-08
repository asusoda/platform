import { Bot, Link2 } from 'lucide-react';
import {
  Card,
  CardHeader,
  Code,
  EmptyState,
  ErrorNote,
  PageHeader,
  PageSkeleton,
  Row,
  Stat,
  StatGrid,
  Table,
  Td,
  Th,
  Tr,
} from '../components/ui';
import { compact, timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import { useOverview } from '../lib/queries';

export function AgentsPage() {
  const { prefix } = useCurrentOrg();
  const { data, isLoading, error } = useOverview(prefix);
  if (isLoading) return <PageSkeleton stats />;
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
      <StatGrid>
        <Stat label="Conversations this week" value={compact(a.active_7_days)} sub={`${compact(a.conversations)} kept`} />
        <Stat label="Members this week" value={compact(a.members_7_days)} />
        <Stat label="Memories" value={compact(a.memories)} />
        <Stat label="Waiting for confirmation" value={a.pending_actions} />
      </StatGrid>
      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader title="Agent tokens" hint="Agents call the platform with these" />
          {agents.length ? (
            <Table>
              <thead>
                <tr>
                  <Th>Name</Th>
                  <Th className="hidden sm:table-cell">Scopes</Th>
                  <Th className="text-right">Last used</Th>
                </tr>
              </thead>
              <tbody>
                {agents.map((t) => (
                  <Tr key={t.name}>
                    <Td className="font-medium">{t.name}</Td>
                    <Td className="hidden sm:table-cell">
                      <div className="flex flex-wrap gap-1">
                        {t.scopes.map((scope) => (
                          <Code key={scope}>{scope}</Code>
                        ))}
                      </div>
                    </Td>
                    <Td className="text-right text-xs whitespace-nowrap text-muted tabular-nums">{timeAgo(t.last_used_at)}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <EmptyState icon={Bot}>No agent tokens. Create one under Tokens.</EmptyState>
          )}
        </Card>
        <Card>
          <CardHeader title="Linked accounts" hint="Members who connected an account for agents to use" />
          {linked.length ? (
            linked.map(([provider, count]) => (
              <Row key={provider}>
                <span className="flex-1 text-sm capitalize">{provider}</span>
                <span className="text-sm font-medium tabular-nums">{count}</span>
              </Row>
            ))
          ) : (
            <EmptyState icon={Link2}>No linked accounts.</EmptyState>
          )}
        </Card>
      </div>
    </>
  );
}
