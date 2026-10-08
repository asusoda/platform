import { useInfiniteQuery } from '@tanstack/react-query';
import { ActivityList } from '../components/activity-list';
import { Button, Card, ErrorNote, Loading, PageHeader } from '../components/ui';
import { api } from '../lib/api';
import { useCurrentOrg } from '../lib/org';
import type { AuditEntry } from '../lib/types';

const PAGE = 50;

export function ActivityPage() {
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
      <PageHeader title="Activity" description="Every change an officer, token or job made in this organization." />
      {log.error ? <ErrorNote error={log.error} /> : null}
      {log.isLoading ? (
        <Loading />
      ) : (
        <Card>
          <ActivityList entries={entries} empty="Nothing recorded yet." />
        </Card>
      )}
      {log.hasNextPage ? (
        <div className="mt-4 flex justify-center">
          <Button onClick={() => log.fetchNextPage()} disabled={log.isFetchingNextPage}>
            Load more
          </Button>
        </div>
      ) : null}
    </>
  );
}
