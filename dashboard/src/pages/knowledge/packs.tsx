import { useMutation, useQuery } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { Badge, Button, Card, CardHeader, ErrorNote, Spinner, quietLink } from '../../components/ui';
import { api, send } from '../../lib/api';
import { REPO_URL } from '../../lib/links';
import { useInvalidate } from './shared';

type Pack = {
  name: string;
  title: string;
  description: string;
  key_prefix: string;
  pages: number;
  queries: string[];
  sources: number;
};

export function SourcePacks({ prefix, onSynced }: { prefix: string; onSynced: (message: string) => void }) {
  const invalidate = useInvalidate(prefix);
  const packs = useQuery({
    queryKey: ['knowledge', prefix, 'packs'],
    queryFn: () => api<{ packs: Pack[] }>(`/api/dashboard/${prefix}/knowledge/packs`),
    enabled: Boolean(prefix),
  });
  const sync = useMutation({
    mutationFn: (pack: Pack) =>
      send<{ added: number; updated: number; retired: number }>(`/api/dashboard/${prefix}/knowledge/packs/${pack.name}/sync`, 'POST'),
    onSuccess: (r, pack) => {
      invalidate();
      onSynced(
        `${pack.title}: ${r.added} added, ${r.updated} updated, ${r.retired} retired. The crawl job fetches due pages in batches every 10 minutes.`,
      );
    },
  });
  if (!packs.data?.packs.length) return null;
  return (
    <Card className="mb-6">
      <CardHeader
        title="Packs"
        hint="Content for a campus or topic: pages crawled on a schedule and live queries for agents. Sync again after Platform updates."
        action={
          <a className={quietLink} href={`${REPO_URL}/tree/main/packs#write-a-pack`} target="_blank" rel="noreferrer">
            Write a pack
          </a>
        }
      />
      {packs.data.packs.map((pack) => (
        <div key={pack.name} className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-4 py-3 last:border-0">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-sm font-medium">
              {pack.title}
              <Badge className="font-mono font-normal">{pack.key_prefix}</Badge>
            </div>
            <div className="mt-0.5 text-xs text-pretty text-muted">{pack.description}</div>
            <div className="mt-0.5 text-xs text-muted tabular-nums">
              {pack.pages} pages, {pack.queries.length} live queries
            </div>
          </div>
          <span className="text-xs text-muted tabular-nums">{pack.sources ? `${pack.sources} sources` : 'not added'}</span>
          <Button onClick={() => sync.mutate(pack)} disabled={sync.isPending}>
            {sync.isPending && sync.variables?.name === pack.name ? <Spinner /> : <RefreshCw className="size-4" />}
            {pack.sources ? 'Sync' : 'Add'}
          </Button>
        </div>
      ))}
      {sync.error ? (
        <div className="p-4 pt-0">
          <ErrorNote error={sync.error} />
        </div>
      ) : null}
    </Card>
  );
}
