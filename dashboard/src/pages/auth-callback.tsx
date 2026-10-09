import { useEffect, useRef, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router';
import { AuthFrame } from '../components/auth-frame';
import { Spinner } from '../components/ui';
import { exchangeLoginCode } from '../lib/api';

export function AuthCallbackPage() {
  const [params] = useSearchParams();
  const [state, setState] = useState<'working' | 'done' | string>('working');
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const code = params.get('code');
    const error = params.get('error');
    if (error || !code) {
      setState(error ?? 'Discord sent no sign-in code.');
      return;
    }
    exchangeLoginCode(code)
      .then(() => setState('done'))
      .catch((e: Error) => setState(e.message));
  }, [params]);

  if (state === 'done') return <Navigate to="/" replace />;
  if (state !== 'working') return <Navigate to={`/login?error=${encodeURIComponent(state)}`} replace />;
  return (
    <AuthFrame>
      <div role="status" className="flex flex-col items-center gap-3 text-center">
        <Spinner className="size-5" />
        <p className="text-sm text-muted">Platform signs you in.</p>
      </div>
    </AuthFrame>
  );
}
