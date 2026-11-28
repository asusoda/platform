import { useInfiniteQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { ActivityList } from '../../components/activity-list';
import { Button, Card, ErrorNote, PageHeader, Select, SkeletonRows } from '../../components/ui';
import { api } from '../../lib/api';
import type { AuditEntry } from '../../lib/types';
import { useOrgPrefixes } from './shared';

const PAGE = 50;

// The audit log of every org and of the server, newest first, 50 at a time.
export function AuditPage() {
  const prefixes = useOrgPrefixes();
  const [org, setOrg] = useState('');
  const log = useInfiniteQuery({
    queryKey: ['superadmin-audit', org],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: String(PAGE) });
      if (org) params.set('org', org);
      if (pageParam) params.set('before_id', String(pageParam));
      return api<{ entries: AuditEntry[] }>(`/api/superadmin/audit?${params}`);
    },
    getNextPageParam: (last) => (last.entries.length === PAGE ? last.entries[last.entries.length - 1].id : undefined),
  });
  const entries = log.data?.pages.flatMap((p) => p.entries) ?? [];
  return (
    <>
      <PageHeader
        action={
          <Select value={org} onChange={(e) => setOrg(e.target.value)} aria-label="Filter by org" className="w-44 sm:w-52">
            <option value="">All organizations</option>
            {prefixes.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </Select>
        }
      />
      <Card>
        {log.error ? (
          <div className="p-4">
            <ErrorNote error={log.error} />
          </div>
        ) : log.isLoading ? (
          <SkeletonRows rows={6} />
        ) : (
          <ActivityList entries={entries} empty="Nothing recorded yet." showOrg={!org} />
        )}
      </Card>
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
