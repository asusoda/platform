import { useQuery } from '@tanstack/react-query';
import { CalendarClock, Cpu, History, Terminal } from 'lucide-react';
import { useParams, useSearchParams } from 'react-router';
import { AuthFrame } from '../../components/auth-frame';
import { Badge, Card, CardHeader, Code, EmptyState, ErrorNote, SkeletonRows } from '../../components/ui';
import { ApiError } from '../../lib/api';
import { timeAgo, when } from '../../lib/format';
import { memberApi, memberLoginUrl } from '../member-store/shared';

export type MemberGodfather = {
  organization: { name: string; prefix: string };
  pods: { id: string; name: string; status: string; is_public: boolean; image_current: boolean }[];
  sessions: { pod_id: string; pod_name: string; title: string; start_at: string; stop_at: string }[];
  connections: { pod_id: string; pod_name: string | null; is_admin: boolean; created_at: string }[];
  cli: { package: string; install: string };
};

const STATUS_TONE: Record<string, 'ok' | 'warn' | 'muted'> = { RUNNING: 'ok', EXITED: 'muted', UNKNOWN: 'warn' };

// The member page of Godfather: the member's pods, next sessions and recent connections, after Discord sign-in.
export function MemberGodfatherPage() {
  const prefix = useParams().prefix ?? '';
  const signInError = useSearchParams()[0].get('error');
  const page = useQuery({
    queryKey: ['member-godfather', prefix],
    queryFn: () => memberApi<MemberGodfather>(`/api/compute/${encodeURIComponent(prefix)}/me`),
    retry: false,
  });
  const signedOut = page.error instanceof ApiError && page.error.status === 401;
  const data = page.data;

  return (
    <AuthFrame width="max-w-3xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">My pods</h1>
          <p className="mt-1 text-sm text-pretty text-muted">
            {data ? `${data.organization.name} Godfather pods you can connect to.` : 'Godfather pods you can connect to.'}
          </p>
        </div>
      </div>
      {signInError ? (
        <div className="mb-4">
          <ErrorNote error={signInError} />
        </div>
      ) : null}
      {page.isLoading ? (
        <Card>
          <SkeletonRows rows={3} />
        </Card>
      ) : signedOut ? (
        <Card className="p-6">
          <p className="text-sm text-pretty text-muted">Sign in with the Discord account that is in the org's server.</p>
          <a
            href={memberLoginUrl(prefix, 'godfather')}
            className="mt-4 inline-flex h-9 items-center rounded-lg bg-fg px-3 text-sm font-medium text-bg hover:opacity-90"
          >
            Sign in with Discord
          </a>
        </Card>
      ) : page.error || !data ? (
        <ErrorNote error={page.error} />
      ) : (
        <div className="space-y-6">
          <Card>
            <CardHeader title="Pods" />
            {data.pods.length ? (
              <ul className="divide-y divide-line">
                {data.pods.map((p) => (
                  <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                    <span className="font-medium">{p.name}</span>
                    <span className="flex gap-1.5">
                      {p.image_current ? null : <Badge tone="warn">Old image</Badge>}
                      <Badge tone={STATUS_TONE[p.status] ?? 'muted'}>{p.status.toLowerCase()}</Badge>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState icon={Cpu} title="No pods yet">
                An officer gives you access to a pod.
              </EmptyState>
            )}
          </Card>
          <Card>
            <CardHeader title="Next sessions" />
            {data.sessions.length ? (
              <ul className="divide-y divide-line">
                {data.sessions.map((s) => (
                  <li key={`${s.pod_id}-${s.start_at}`} className="flex flex-wrap justify-between gap-2 px-4 py-3 text-sm">
                    <span>
                      <span className="font-medium">{s.title}</span> <span className="text-muted">on {s.pod_name}</span>
                    </span>
                    <span className="text-muted tabular-nums">{when(s.start_at)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState icon={CalendarClock} title="No sessions scheduled" />
            )}
          </Card>
          <Card>
            <CardHeader title="Recent connections" />
            {data.connections.length ? (
              <ul className="divide-y divide-line">
                {data.connections.map((c) => (
                  <li key={`${c.pod_id}-${c.created_at}`} className="flex justify-between gap-2 px-4 py-3 text-sm">
                    <span>
                      {c.pod_name ?? c.pod_id} {c.is_admin ? <Badge tone="warn">root</Badge> : null}
                    </span>
                    <span className="text-muted">{timeAgo(c.created_at)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState icon={History} title="No connections yet" />
            )}
          </Card>
          <Card>
            <CardHeader title="Connect" />
            <ol className="space-y-2 p-4 text-sm">
              {[data.cli.install, `godfather auth --org ${prefix}`, `godfather connect --org ${prefix}`].map((command) => (
                <li key={command} className="flex items-center gap-2">
                  <Terminal className="size-4 shrink-0 text-muted" /> <Code>{command}</Code>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      )}
    </AuthFrame>
  );
}
