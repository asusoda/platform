import { useEffect, useRef, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router';
import { exchangeLoginCode } from '../lib/api';
import { Spinner } from '../components/ui';

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
      setState(error ?? 'No login code was returned');
      return;
    }
    exchangeLoginCode(code)
      .then(() => setState('done'))
      .catch((e: Error) => setState(e.message));
  }, [params]);

  if (state === 'done') return <Navigate to="/" replace />;
  if (state !== 'working') return <Navigate to={`/login?error=${encodeURIComponent(state)}`} replace />;
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner />
    </div>
  );
}
