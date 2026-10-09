import { useQuery } from '@tanstack/react-query';
import { History, RefreshCw, ShieldCheck, Wifi } from 'lucide-react';
import type { ReactNode } from 'react';
import { Badge, Button, Dialog, Dot, EmptyState, ErrorNote, Mono, SkeletonRows, Spinner, Table, Td, Th, Tr } from '../../components/ui';
import { api } from '../../lib/api';
import { elapsed, timeAgo, when } from '../../lib/format';
import type { Pod, PodConnected, PodMembers } from '../../lib/types';
import { podPath } from './shared';

function Person({ name, id, sub }: { name: string | null; id: string | null; sub?: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="truncate text-sm font-medium">{name ?? (id ? <Mono>{id}</Mono> : 'Unknown member')}</div>
      {sub ? <div className="truncate text-xs text-muted">{sub}</div> : null}
    </div>
  );
}

function Section({ icon: Icon, title, hint, action, children }: { icon: typeof Wifi; title: string; hint?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-line">
      <div className="flex items-center justify-between gap-3 border-b border-line px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <Icon className="size-4 shrink-0 text-muted" />
          <div className="min-w-0">
            <h3 className="truncate text-sm font-medium">{title}</h3>
            {hint ? <p className="truncate text-xs text-muted">{hint}</p> : null}
          </div>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function ConnectedNow({ prefix, pod }: { prefix: string; pod: Pod }) {
  const live = useQuery({
    queryKey: ['compute', prefix, 'connected', pod.id],
    queryFn: () => api<PodConnected>(`${podPath(prefix, pod.id)}/members/connected`),
    enabled: pod.status === 'RUNNING',
    retry: false,
  });
  const refresh = (
    <Button variant="ghost" size="icon" title="Check again" aria-label="Check again" onClick={() => live.refetch()} disabled={live.isFetching || pod.status !== 'RUNNING'}>
      {live.isFetching ? <Spinner className="size-3.5" /> : <RefreshCw className="size-4" />}
    </Button>
  );
  const unknown = (reason: string) => (
    <div className="flex items-start gap-2 px-3 py-3 text-sm">
      <Badge tone="warn">
        <Dot tone="warn" />
        Unknown
      </Badge>
      <span className="text-muted">{reason}</span>
    </div>
  );
  let body: ReactNode;
  if (pod.status !== 'RUNNING') body = unknown('The pod is not running.');
  else if (live.isLoading) body = <div className="flex items-center gap-2 px-3 py-3 text-sm text-muted"><Spinner className="size-3.5" /> Checking the pod</div>;
  else if (live.error || !live.data) body = unknown('The pod did not answer.');
  else if (live.data.state === 'unknown') body = unknown(live.data.reason ?? 'The sessions on the pod cannot be read.');
  else if (!live.data.sessions.length) body = <p className="px-3 py-3 text-sm text-muted">Nobody is connected.</p>;
  else
    body = (
      <ul className="divide-y divide-line">
        {live.data.sessions.map((s, i) => (
          <li key={`${s.username}-${i}`} className="flex items-center justify-between gap-3 px-3 py-2">
            <div className="flex min-w-0 items-center gap-2">
              <Dot tone="ok" />
              <Person name={s.name ?? s.username} id={s.discord_id} sub={<Mono>{s.username}</Mono>} />
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {s.is_admin ? <Badge tone="active">Root</Badge> : null}
              <span className="text-xs text-muted tabular-nums">{elapsed(s.seconds)}</span>
            </div>
          </li>
        ))}
      </ul>
    );
  return (
    <Section icon={Wifi} title="Connected now" hint="Live SSH sessions on the pod" action={refresh}>
      {body}
    </Section>
  );
}

function Access({ data, onEdit }: { data: PodMembers['access']; onEdit: () => void }) {
  const edit = (
    <Button variant="ghost" onClick={onEdit}>
      Change
    </Button>
  );
  return (
    <Section icon={ShieldCheck} title="Access" hint="Officers can always connect, as root" action={edit}>
      {data.is_public ? (
        <p className="flex items-center gap-2 px-3 py-3 text-sm">
          <Badge tone="ok">All members</Badge>
          <span className="text-muted">Every member of the Discord server can connect while it runs.</span>
        </p>
      ) : data.allowed.length ? (
        <ul className="max-h-48 divide-y divide-line overflow-y-auto">
          {data.allowed.map((p) => (
            <li key={p.discord_id} className="px-3 py-2">
              <Person name={p.name} id={p.discord_id} sub={p.name ? <Mono>{p.discord_id}</Mono> : null} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="px-3 py-3 text-sm text-muted">Only officers can connect.</p>
      )}
    </Section>
  );
}

function Recent({ data }: { data: PodMembers['recent'] }) {
  return (
    <Section icon={History} title="Recent connections" hint="Each certificate the CLI got for this pod, last 90 days">
      {data.length ? (
        <div className="max-h-72 overflow-y-auto">
          <Table>
            <thead>
              <tr>
                <Th>Member</Th>
                <Th className="hidden sm:table-cell">Folder</Th>
                <Th className="text-right">When</Th>
              </tr>
            </thead>
            <tbody>
              {data.map((c, i) => (
                <Tr key={`${c.discord_id}-${c.created_at}-${i}`}>
                  <Td className="w-full max-w-0">
                    <div className="flex items-center gap-2">
                      <Person name={c.name ?? c.username} id={c.discord_id} />
                      {c.is_admin ? <Badge tone="active">Root</Badge> : null}
                    </div>
                  </Td>
                  <Td className="hidden whitespace-nowrap sm:table-cell">
                    <Mono>{c.username}</Mono>
                  </Td>
                  <Td className="text-right text-xs whitespace-nowrap text-muted tabular-nums" title={c.created_at ? when(c.created_at) : undefined}>
                    {timeAgo(c.created_at)}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </div>
      ) : (
        <EmptyState icon={History}>Nobody connected in the last 90 days.</EmptyState>
      )}
    </Section>
  );
}

// Who can connect to a pod, who is connected now and who connected recently.
export function PodMembersDialog({ prefix, pod, onClose, onEditAccess }: { prefix: string; pod: Pod; onClose: () => void; onEditAccess: () => void }) {
  const members = useQuery({
    queryKey: ['compute', prefix, 'pod-members', pod.id],
    queryFn: () => api<PodMembers>(`${podPath(prefix, pod.id)}/members`),
  });
  return (
    <Dialog open onClose={onClose} title={`Members of ${pod.name}`} description="Who can connect with the compute CLI, who is connected now and who connected before." wide>
      <div className="space-y-4">
        <ConnectedNow prefix={prefix} pod={pod} />
        {members.isLoading ? (
          <SkeletonRows rows={3} />
        ) : members.error || !members.data ? (
          <ErrorNote error={members.error} />
        ) : (
          <>
            <Access data={members.data.access} onEdit={onEditAccess} />
            <Recent data={members.data.recent} />
          </>
        )}
      </div>
    </Dialog>
  );
}
