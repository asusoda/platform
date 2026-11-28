import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Layers, Plus } from 'lucide-react';
import { AsuSignIn } from '../../components/asu-signin';
import { Tooltip } from '../../components/tooltip';
import { SharedApps } from './shared-apps';
import { Badge, Button, Card, EmptyState, ErrorNote, PageSkeleton, Spinner } from '../../components/ui';
import { api, send } from '../../lib/api';
import { count, timeAgo } from '../../lib/format';
import { PAID_BY } from '../../lib/limits';
import { useModuleCatalog } from '../../lib/queries';
import type { Submodule } from '../../lib/types';

export const submodulesKey = (prefix: string) => ['submodules', prefix];

// The shared sub-modules an org can subscribe to, such as knowledge.asu or feeds.jobs.
export function useSubmodules(prefix: string) {
  return useQuery({
    queryKey: submodulesKey(prefix),
    queryFn: () => api<{ submodules: Submodule[] }>(`/api/dashboard/${prefix}/submodules`),
  });
}

// Subscribe or end a subscription, which turns the sub-module's switch on or off. Invalidates the lists that read
// it: the module catalog, knowledge and feed presets.
export function useSubscription(prefix: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ name, on }: { name: string; on: boolean }) =>
      send(`/api/dashboard/${prefix}/submodules/${name}/subscription`, on ? 'PUT' : 'DELETE'),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: submodulesKey(prefix) });
      client.invalidateQueries({ queryKey: ['catalog', prefix] });
      client.invalidateQueries({ queryKey: ['knowledge', prefix] });
      client.invalidateQueries({ queryKey: ['feeds', prefix] });
    },
  });
}

const PART_NAME = { pages: ['page', 'pages'], queries: ['live query', 'live queries'], feeds: ['feed', 'feeds'] } as const;

// What a shared sub-module brings, and who pays for each part.
function Parts({ s }: { s: Submodule }) {
  if (!s.parts.length) return <p className="mt-3 text-xs text-muted">No parts yet</p>;
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {s.parts.map((p) => (
        <Tooltip key={p.kind} label={PAID_BY[p.paid_by].text} side="top">
          <Badge tone={p.paid_by === 'shared' ? 'ok' : 'muted'}>
            {count(p.count)} {PART_NAME[p.kind][p.count === 1 ? 0 : 1]} · {PAID_BY[p.paid_by].title.toLowerCase()}
          </Badge>
        </Tooltip>
      ))}
    </div>
  );
}

function matchesQuery(s: Submodule, query: string): boolean {
  const q = query.trim().toLowerCase();
  return !q || `${s.title} ${s.description} ${s.key}`.toLowerCase().includes(q);
}

export function SubmodulesTab({ prefix, query }: { prefix: string; query: string }) {
  const submodules = useSubmodules(prefix);
  const catalog = useModuleCatalog(prefix);
  const change = useSubscription(prefix);
  if (submodules.isLoading) return <PageSkeleton />;
  if (submodules.error || !submodules.data) return <ErrorNote error={submodules.error ?? 'No data'} />;
  const titles = new Map((catalog.data?.modules ?? []).map((m) => [m.name, m]));
  // The ASU sign-in shows once its own sub-module is on
  const signIn = (catalog.data?.modules ?? []).flatMap((m) => m.submodules).find((s) => s.key === 'knowledge.asu_signin');
  const list = submodules.data.submodules.filter((s) => matchesQuery(s, query));
  return (
    <div className="space-y-4">
      <SharedApps prefix={prefix} query={query} />
      <h2 className="text-xs font-medium tracking-wide text-muted uppercase">Content</h2>
      {change.error ? <ErrorNote error={change.error} /> : null}
      {!list.length ? (
        <Card>
          <EmptyState icon={Layers} title="No shared content matches">
            Clear the search to see all shared content.
          </EmptyState>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {list.map((s) => {
            const busy = change.isPending && change.variables?.name === s.name;
            return (
              <Card key={s.key} className="flex flex-col p-4" data-submodule={s.key}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-semibold">{s.title}</h3>
                    <p className="mt-1 line-clamp-2 text-sm text-pretty text-muted">{s.description}</p>
                  </div>
                  {s.subscribed ? <Badge tone="ok">Subscribed</Badge> : null}
                </div>
                <Parts s={s} />
                {s.modules.length ? (
                  <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Features that read it">
                    {s.modules.map((name) => {
                      const m = titles.get(name);
                      return (
                        <Badge key={name} tone={m?.enabled ? 'active' : 'muted'}>
                          {m?.title ?? name}
                          {m && !m.enabled ? ' (off)' : ''}
                        </Badge>
                      );
                    })}
                  </div>
                ) : null}
                {s.key === 'knowledge.asu' && s.subscribed && signIn?.enabled ? <AsuSignIn prefix={prefix} /> : null}
                <div className="mt-auto flex items-center justify-between gap-3 pt-4">
                  <span className="text-xs text-muted tabular-nums">
                    {s.subscribers} {s.subscribers === 1 ? 'org' : 'orgs'}
                    {s.last_crawl ? ` · crawled ${timeAgo(s.last_crawl)}` : ''}
                  </span>
                  {s.subscribed ? (
                    <Button variant="ghost" size="sm" disabled={busy} onClick={() => change.mutate({ name: s.name, on: false })}>
                      {busy ? <Spinner className="size-3.5" /> : null} Unsubscribe
                    </Button>
                  ) : (
                    <Button size="sm" disabled={busy} onClick={() => change.mutate({ name: s.name, on: true })}>
                      {busy ? <Spinner className="size-3.5" /> : <Plus className="size-3.5" />} Subscribe
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
