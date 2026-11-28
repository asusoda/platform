import { useQuery } from '@tanstack/react-query';
import { Package } from 'lucide-react';
import { useState } from 'react';
import { Badge, Button, Card, Dialog, EmptyState, ErrorNote, Mono, PageHeader, SkeletonRows, Table, Td, Th, Tr } from '../../components/ui';
import { api } from '../../lib/api';
import type { SubmoduleOverview } from '../../lib/types';

// Every submodule with the orgs that subscribe, its shared pages and passages, and the pages that fail to crawl.
export function SubmodulesPage() {
  const [open, setOpen] = useState<SubmoduleOverview | null>(null);
  const list = useQuery({
    queryKey: ['superadmin-submodules'],
    queryFn: () => api<{ submodules: SubmoduleOverview[] }>('/api/superadmin/submodules').then((b) => b.submodules),
  });
  const rows = list.data ?? [];
  return (
    <>
      <PageHeader />
      <Card>
        {list.error ? (
          <div className="p-4">
            <ErrorNote error={list.error} />
          </div>
        ) : list.isLoading ? (
          <SkeletonRows rows={3} />
        ) : rows.length ? (
          <Table>
            <thead>
              <tr>
                <Th>Sub-module</Th>
                <Th className="hidden sm:table-cell">Status</Th>
                <Th className="hidden text-right md:table-cell">Orgs</Th>
                <Th className="hidden text-right md:table-cell">Pages</Th>
                <Th className="hidden text-right lg:table-cell">Passages</Th>
                <Th className="text-right">Failing</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <Tr key={s.key}>
                  <Td className="w-full max-w-0">
                    <div className="truncate font-medium">{s.title}</div>
                    <Mono className="block truncate">
                      {s.key}
                      {s.origin === 'code' ? '' : `, ${s.origin}`}
                    </Mono>
                  </Td>
                  <Td className="hidden sm:table-cell">
                    <Badge tone={s.status === 'shared' ? 'ok' : 'muted'}>{s.status}</Badge>
                  </Td>
                  <Td className="hidden text-right text-muted tabular-nums md:table-cell">{s.subscribers}</Td>
                  <Td className="hidden text-right text-muted tabular-nums md:table-cell">{s.sources}</Td>
                  <Td className="hidden text-right text-muted tabular-nums lg:table-cell">{s.passages.toLocaleString()}</Td>
                  <Td className="text-right">
                    {s.failing.length ? (
                      <Button variant="ghost" className="h-7 px-2" onClick={() => setOpen(s)} aria-label={`Failing pages of ${s.title}`}>
                        <Badge tone="bad">{s.failing.length}</Badge>
                      </Button>
                    ) : (
                      <span className="text-muted tabular-nums">0</span>
                    )}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <EmptyState icon={Package} title="No sub-modules" />
        )}
      </Card>
      <Dialog open={open !== null} onClose={() => setOpen(null)} title="Failing pages" description={open?.title} wide>
        {open ? (
          <ul className="max-h-[60vh] space-y-3 overflow-y-auto text-sm">
            {open.failing.map((f) => (
              <li key={f.key} className="min-w-0">
                <Mono className="block truncate text-fg">{f.key}</Mono>
                <p className="mt-0.5 text-xs break-words text-muted">{f.error}</p>
              </li>
            ))}
          </ul>
        ) : null}
      </Dialog>
    </>
  );
}
