import { BookOpen, Bot, Link2 } from 'lucide-react';
import { Link } from 'react-router';
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
import { docsPage } from '../lib/links';
import { useCurrentOrg } from '../lib/org';
import { useOverview } from '../lib/queries';

// The steps an officer follows to connect an agent to the MCP server.
function ConnectCard({ prefix }: { prefix: string }) {
  const steps = [
    <>
      Create a token of kind <Code>agent</Code> on{' '}
      <Link to={`/${prefix}/tokens`} className="text-fg underline underline-offset-2">
        Tokens
      </Link>
      .
    </>,
    <>
      Point the MCP client of the agent at <Code>/mcp</Code> on the MCP server, port <Code>8001</Code> by default.
    </>,
    <>
      Send the token in the <Code>Authorization: Bearer</Code> header.
    </>,
  ];
  return (
    <Card>
      <CardHeader
        title="Connect an agent"
        hint="The agent sees only the tools that its token scopes and the org's modules allow"
        action={
          <a
            href={docsPage('architecture')}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-xs text-muted transition-colors hover:text-fg"
          >
            <BookOpen className="size-3.5" /> Docs
          </a>
        }
      />
      <ol className="space-y-2 px-4 py-3 text-sm">
        {steps.map((step, n) => (
          <li key={n} className="flex gap-2.5">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-panel-2 text-[11px] font-medium tabular-nums">
              {n + 1}
            </span>
            <span className="min-w-0 text-pretty">{step}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}

// Agents call Platform over MCP and keep member data in the agents module. The page shows counts only.
export function McpPage() {
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
        title="MCP"
        description="Agents that connect to Platform over MCP: their tokens, scopes, linked accounts and activity."
      />
      <section aria-label="Agent activity">
        <div className="mb-3">
          <h2 className="text-sm font-semibold">Agent activity</h2>
          <p className="mt-0.5 text-xs text-muted">Counts only. Officers cannot read member conversations or memories.</p>
        </div>
        <StatGrid>
          <Stat label="Conversations this week" value={compact(a.active_7_days)} sub={`${compact(a.conversations)} kept`} />
          <Stat label="Members this week" value={compact(a.members_7_days)} />
          <Stat label="Memories" value={compact(a.memories)} />
          <Stat label="Waiting for confirmation" value={a.pending_actions} />
        </StatGrid>
      </section>
      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader title="Agent tokens" hint="Agents call Platform and its MCP server with these" />
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
        <div className="space-y-6">
          <ConnectCard prefix={prefix} />
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
      </div>
    </>
  );
}
