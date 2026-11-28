import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Building2 } from 'lucide-react';
import { Badge, Card, EmptyState, ErrorNote, Mono, PageHeader, SkeletonRows, Switch, Table, Td, Th, Tr } from '../../components/ui';
import { api, send } from '../../lib/api';
import { useAdminOrgs } from './shared';

type Publisher = { org_id: number; prefix: string; source: 'env' | 'superadmin' };
type Publishers = { publishers: Publisher[] };

const KEY = ['superadmin-publishers'];

// Orgs that may write knowledge every org can search. KNOWLEDGE_PUBLISHERS in .env adds orgs the page cannot remove.
export function PublishersPage() {
  const client = useQueryClient();
  const orgs = useAdminOrgs();
  const list = useQuery({ queryKey: KEY, queryFn: () => api<Publishers>('/api/superadmin/publishers') });
  const change = useMutation({
    mutationFn: ({ id, on }: { id: number; on: boolean }) => send<Publishers>(`/api/superadmin/publishers/${id}`, 'PUT', { publisher: on }),
    onSuccess: (body) => client.setQueryData(KEY, body),
  });
  const byId = new Map((list.data?.publishers ?? []).map((p) => [p.org_id, p]));
  const error = list.error ?? orgs.error ?? change.error;
  return (
    <>
      <PageHeader title="Knowledge publishers" docs="modules/knowledge" />
      <Card>
        {error ? (
          <div className="p-4">
            <ErrorNote error={error} />
          </div>
        ) : null}
        {list.isLoading || orgs.isLoading ? (
          <SkeletonRows rows={3} />
        ) : orgs.data?.length ? (
          <Table>
            <thead>
              <tr>
                <Th>Organization</Th>
                <Th className="text-right">Publisher</Th>
              </tr>
            </thead>
            <tbody>
              {orgs.data.map((o) => {
                const p = byId.get(o.id);
                return (
                  <Tr key={o.id}>
                    <Td className="w-full max-w-0">
                      <div className="truncate font-medium">{o.name}</div>
                      <Mono className="truncate">{o.prefix}</Mono>
                    </Td>
                    <Td>
                      <div className="flex items-center justify-end gap-2">
                        {p?.source === 'env' ? <Badge>Set in .env</Badge> : null}
                        <Switch
                          checked={Boolean(p)}
                          disabled={p?.source === 'env' || change.isPending}
                          onChange={(on) => change.mutate({ id: o.id, on })}
                          label={`${o.name} is a publisher`}
                        />
                      </div>
                    </Td>
                  </Tr>
                );
              })}
            </tbody>
          </Table>
        ) : (
          <EmptyState icon={Building2} title="No organizations" />
        )}
      </Card>
    </>
  );
}
