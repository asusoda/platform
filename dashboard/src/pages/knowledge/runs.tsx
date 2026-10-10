import { useQuery } from '@tanstack/react-query';
import { ScrollText } from 'lucide-react';
import { useState } from 'react';
import {
  Badge,
  Card,
  CardHeader,
  Dot,
  EmptyState,
  ErrorNote,
  Select,
  ShowMore,
  SkeletonRows,
  Table,
  Td,
  Th,
  Tr,
  useShowMore,
} from '../../components/ui';
import { api } from '../../lib/api';
import { timeAgo } from '../../lib/format';
import { useCurrentOrg } from '../../lib/org';
import type { KnowledgeRun } from '../../lib/types';

function result(r: KnowledgeRun): string {
  if (r.error) return 'failed';
  if (!r.changed) return `unchanged, ${r.chunks ?? 0} passages`;
  return `indexed ${r.chunks ?? 0} passages`;
}

// The latest crawls and uploads of the org, newest first.
export function KnowledgeRuns() {
  const { prefix } = useCurrentOrg();
  const [failed, setFailed] = useState(false);
  const runs = useQuery({
    queryKey: ['knowledge', prefix, 'runs', failed],
    queryFn: () => api<{ runs: KnowledgeRun[] }>(`/api/dashboard/${prefix}/knowledge/runs?limit=200${failed ? '&failed=1' : ''}`),
    enabled: Boolean(prefix),
    refetchInterval: 15_000,
  });
  const list = runs.data?.runs ?? [];
  const page = useShowMore(list, failed, 50);
  return (
    <>
      {runs.error ? (
        <div className="mb-4">
          <ErrorNote error={runs.error} />
        </div>
      ) : null}
      <Card>
        <CardHeader
          title="Knowledge runs"
          hint="Each crawl and upload: whether the index changed, the passages it holds, and the error if it failed. The last 500 are kept."
          action={
            <Select value={failed ? 'failed' : 'all'} onChange={(e) => setFailed(e.target.value === 'failed')} aria-label="Show" className="h-8 w-auto text-xs">
              <option value="all">All runs</option>
              <option value="failed">Failed only</option>
            </Select>
          }
        />
        {runs.isLoading ? (
          <SkeletonRows rows={8} />
        ) : list.length ? (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Source</Th>
                  <Th className="hidden sm:table-cell">Kind</Th>
                  <Th>Result</Th>
                  <Th className="hidden text-right md:table-cell">Took</Th>
                  <Th className="text-right">When</Th>
                </tr>
              </thead>
              <tbody>
                {page.shown.map((r) => (
                  <Tr key={r.id}>
                    <Td className="max-w-0 py-2.5 sm:w-1/3">
                      <span className="flex items-center gap-2">
                        <Dot tone={r.error ? 'bad' : r.changed ? 'ok' : 'muted'} />
                        <span className="truncate font-mono text-xs" title={r.source_key}>
                          {r.source_key}
                        </span>
                      </span>
                    </Td>
                    <Td className="hidden sm:table-cell">
                      <Badge>{r.kind}</Badge>
                    </Td>
                    <Td className="text-sm">
                      {result(r)}
                      {r.error ? <div className="line-clamp-2 text-xs text-bad" title={r.error}>{r.error}</div> : null}
                    </Td>
                    <Td className="hidden text-right text-xs whitespace-nowrap text-muted tabular-nums md:table-cell">
                      {(r.duration_ms / 1000).toFixed(1)}s
                    </Td>
                    <Td className="text-right text-xs whitespace-nowrap text-muted tabular-nums">{timeAgo(r.started_at)}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
            <ShowMore list={page} noun="runs" />
          </>
        ) : (
          <EmptyState icon={ScrollText} title={failed ? 'No failed runs' : 'No runs yet'}>
            Crawls and uploads show here when they run.
          </EmptyState>
        )}
      </Card>
    </>
  );
}
