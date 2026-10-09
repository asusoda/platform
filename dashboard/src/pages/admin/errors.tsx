import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bug } from 'lucide-react';
import { useState } from 'react';
import { ErrorList } from '../../components/error-list';
import { Card, CardHeader, EmptyState, ErrorNote, Select, SkeletonRows } from '../../components/ui';
import { api, send } from '../../lib/api';
import type { ErrorGroup } from '../../lib/types';

const SERVER = '(server)';

// Open errors of every org and of the server, such as failed jobs. Only the superadmin sees them.
export function ErrorsCard({ prefixes }: { prefixes: string[] }) {
  const client = useQueryClient();
  const [org, setOrg] = useState('');
  const list = useQuery({
    queryKey: ['superadmin-errors', org],
    queryFn: () => {
      const params = new URLSearchParams({ status: 'open', limit: '200' });
      if (org && org !== SERVER) params.set('org', org);
      return api<{ errors: ErrorGroup[] }>(`/api/superadmin/errors?${params}`);
    },
    refetchInterval: 30_000,
  });
  const change = useMutation({
    mutationFn: ({ action, ids }: { action: 'resolve' | 'reopen'; ids: number[] }) =>
      send(`/api/superadmin/errors/${action}`, 'POST', { ids }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['superadmin-errors'] }),
  });
  const errors = (list.data?.errors ?? []).filter((e) => org !== SERVER || e.org === null);
  return (
    <Card>
      <CardHeader
        title="Errors"
        hint="Open errors of every organization, and of the server itself, such as failed jobs."
        action={
          <Select value={org} onChange={(e) => setOrg(e.target.value)} aria-label="Filter by org" className="h-8 w-40 text-xs sm:w-48">
            <option value="">All</option>
            <option value={SERVER}>Server only</option>
            {prefixes.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </Select>
        }
      />
      {list.error ? (
        <div className="p-4">
          <ErrorNote error={list.error} />
        </div>
      ) : list.isLoading ? (
        <SkeletonRows rows={4} />
      ) : errors.length ? (
        <ErrorList errors={errors} showOrg={org === ''} busy={change.isPending} onChange={(action, ids) => change.mutate({ action, ids })} />
      ) : (
        <EmptyState icon={Bug} title="No open errors" />
      )}
    </Card>
  );
}
