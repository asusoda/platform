import { useMutation, useQuery } from '@tanstack/react-query';
import { BookOpen, LogIn } from 'lucide-react';
import { useState } from 'react';
import { api, send } from '../lib/api';
import { timeAgo } from '../lib/format';
import { docsPage } from '../lib/links';
import type { AsuState } from '../lib/types';
import { IntegrationIcon } from './integration-icons';
import { Badge, Button, Card, cx, Dialog, ErrorNote, Field, FormActions, Input, Spinner } from './ui';

const POLL_MS = 1000;

function busy(state?: AsuState): boolean {
  return state?.attempt?.state === 'running' || state?.attempt?.state === 'duo_code';
}

function StateBadge({ state }: { state: AsuState }) {
  if (busy(state)) return <Badge tone="active">Signing in</Badge>;
  if (state.signed_in) return <Badge tone="ok">Signed in</Badge>;
  if (state.expired_at) return <Badge tone="bad">Sign-in expired</Badge>;
  return <Badge tone="warn">Not signed in</Badge>;
}

function signedInLine(state: AsuState): string {
  const who = state.signed_in_by ? ` by ${state.signed_in_by}` : '';
  const when = state.signed_in_at ? ` ${timeAgo(state.signed_in_at)}` : '';
  return `Signed in${who}${when}. Agents with the asu:read scope can search Sun Devil Central.`;
}

// The NetID and password go to the API one time. The API does not keep them.
function SignInForm({ prefix, onStarted }: { prefix: string; onStarted: (state: AsuState) => void }) {
  const [netid, setNetid] = useState('');
  const [password, setPassword] = useState('');
  const start = useMutation({
    mutationFn: () => send<AsuState>(`/api/dashboard/${prefix}/integrations/asu/signin`, 'POST', { netid, password }),
    onSuccess: (state) => {
      setPassword('');
      onStarted(state);
    },
  });
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (netid.trim() && password) start.mutate();
      }}
    >
      <Field label="NetID" hint="Your ASU NetID, such as sparky1.">
        <Input autoComplete="username" value={netid} onChange={(e) => setNetid(e.target.value)} />
      </Field>
      <Field label="Password" hint="Sent to ASU one time. Platform keeps only the browser cookies.">
        <Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <FormActions error={start.error}>
        <Button variant="primary" disabled={!netid.trim() || !password || start.isPending}>
          {start.isPending ? <Spinner className="size-3.5" /> : <LogIn className="size-3.5" />} Sign in
        </Button>
      </FormActions>
    </form>
  );
}

// The ASU sign-in: an officer signs in with NetID, password and Duo. Agents then read Sun Devil Central.
export function AsuCard({ prefix, initial }: { prefix: string; initial: AsuState }) {
  const [open, setOpen] = useState(false);
  const live = useQuery({
    queryKey: ['asu-signin', prefix],
    queryFn: () => api<AsuState>(`/api/dashboard/${prefix}/integrations/asu/signin`),
    initialData: initial,
    refetchInterval: (query) => (busy(query.state.data) ? POLL_MS : false),
  });
  const state = live.data ?? initial;
  const attempt = state.attempt;
  const stop = useMutation({
    mutationFn: () => send<AsuState>(`/api/dashboard/${prefix}/integrations/asu/signin`, 'DELETE'),
    onSuccess: () => live.refetch(),
  });
  return (
    <Card className="flex flex-col">
      <div className="flex items-start gap-3 p-4">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-line bg-panel-2/60">
          <IntegrationIcon name="asu" className="size-[18px]" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">{state.title}</h3>
            <StateBadge state={state} />
          </div>
          <p className="mt-1 text-sm text-pretty text-muted">
            Sign in to ASU with a NetID and Duo. Agents then search clubs and events on Sun Devil Central.
          </p>
          {state.signed_in ? <p className="mt-1 text-xs text-muted">{signedInLine(state)}</p> : null}
          {!state.signed_in && state.expired_at ? (
            <p className="mt-1 text-xs text-bad">The sign-in expired {timeAgo(state.expired_at)}. Sign in again.</p>
          ) : null}
        </div>
      </div>
      {attempt && attempt.state !== 'done' ? (
        <div
          role="status"
          className={cx(
            'mx-4 mb-3 animate-in rounded-md px-3 py-2.5 text-xs',
            attempt.state === 'failed' ? 'bg-bad/10 text-bad' : 'border border-line text-fg',
          )}
        >
          {attempt.state === 'duo_code' && attempt.code ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-mono text-2xl font-semibold tracking-[0.2em] text-fg" aria-label="Duo code">
                {attempt.code}
              </span>
              <span className="text-muted">Enter this code in the Duo app on your phone.</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              {attempt.state === 'failed' ? null : <Spinner className="size-3.5" />}
              <span>{attempt.state === 'failed' ? `Sign-in failed: ${attempt.reason ?? attempt.message}` : attempt.message}</span>
            </div>
          )}
        </div>
      ) : null}
      {state.blocked ? <p className="mx-4 mb-3 text-xs text-muted">{state.blocked}</p> : null}
      {stop.error ? (
        <div className="mx-4 mb-3">
          <ErrorNote error={stop.error} />
        </div>
      ) : null}
      <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-line px-4 py-3">
        {state.signed_in ? (
          <Button variant="ghost" disabled={stop.isPending || busy(state)} onClick={() => stop.mutate()}>
            Sign out
          </Button>
        ) : (
          <Button variant="primary" disabled={Boolean(state.blocked) || busy(state)} onClick={() => setOpen(true)}>
            <LogIn className="size-4" /> {state.expired_at ? 'Sign in again' : 'Sign in to ASU'}
          </Button>
        )}
        <a
          href={`${docsPage('integrations')}#sign-in-to-asu`}
          target="_blank"
          rel="noreferrer"
          className="ml-auto flex items-center gap-1 text-xs text-muted transition-colors hover:text-fg"
        >
          <BookOpen className="size-3.5" /> Docs
        </a>
      </div>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Sign in to ASU"
        description="Approve the Duo push on your phone after you sign in. This card shows the Duo code when Duo asks for one."
      >
        <SignInForm
          prefix={prefix}
          onStarted={() => {
            setOpen(false);
            live.refetch();
          }}
        />
      </Dialog>
    </Card>
  );
}
