import { useInfiniteQuery } from '@tanstack/react-query';
import { ActivityList } from '../components/activity-list';
import { useSearchParams } from 'react-router';
import { Button, Card, cx, ErrorNote, PageHeader, SkeletonRows } from '../components/ui';
import { api } from '../lib/api';
import { useCurrentOrg } from '../lib/org';
import type { AuditEntry } from '../lib/types';
import { CiRuns } from './ci';

const PAGE = 50;

const TABS = [
  { id: 'changes', label: 'Changes' },
  { id: 'ci', label: 'CI runs' },
] as const;

export function ActivityPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'ci' ? 'ci' : 'changes';
  return (
    <>
      <PageHeader
        title="Activity"
        description="Every change an officer, token or job made in this organization, and the CI runs of its repositories."
      />
      <div role="tablist" aria-label="Activity" className="mb-6 flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setParams(t.id === 'changes' ? {} : { tab: t.id }, { replace: true })}
            className={cx(
              '-mb-px h-9 border-b-2 px-3 text-sm transition-colors',
              tab === t.id ? 'border-fg font-medium text-fg' : 'border-transparent text-muted hover:text-fg',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'ci' ? <CiRuns /> : <AuditLog />}
    </>
  );
}

function AuditLog() {
  const { org } = useCurrentOrg();
  const log = useInfiniteQuery({
    queryKey: ['audit', org?.id],
    enabled: Boolean(org),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      api<{ entries: AuditEntry[] }>(
        `/api/organizations/${org!.id}/audit?limit=${PAGE}${pageParam ? `&before_id=${pageParam}` : ''}`,
      ),
    getNextPageParam: (last) => (last.entries.length === PAGE ? last.entries[last.entries.length - 1].id : undefined),
  });
  const entries = log.data?.pages.flatMap((p) => p.entries) ?? [];
  return (
    <>
      {log.error ? (
        <div className="mb-4">
          <ErrorNote error={log.error} />
        </div>
      ) : null}
      <Card>
        {log.isLoading || !org ? <SkeletonRows rows={8} /> : <ActivityList entries={entries} empty="Nothing recorded yet." />}
      </Card>
      {log.hasNextPage ? (
        <div className="mt-6 flex justify-center">
          <Button onClick={() => log.fetchNextPage()} disabled={log.isFetchingNextPage}>
            Load more
          </Button>
        </div>
      ) : null}
    </>
  );
}
