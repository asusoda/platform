import { ArrowRight } from 'lucide-react';
import { useSearchParams } from 'react-router';
import { Logo } from '../components/logo';
import { ErrorNote } from '../components/ui';
import { loginUrl } from '../lib/api';

export function LoginPage() {
  const [params] = useSearchParams();
  const error = params.get('error');
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 text-sm font-medium tracking-tight">
          <Logo className="size-5" />
          Platform
        </div>
        <h1 className="mt-8 text-2xl font-semibold tracking-tight">Sign in to the dashboard</h1>
        <p className="mt-2 text-sm text-muted">Use the Discord account that holds your organization's officer role.</p>
        {error ? (
          <div className="mt-6">
            <ErrorNote error={error} />
          </div>
        ) : null}
        <a
          href={loginUrl()}
          className="mt-8 flex h-10 items-center justify-center gap-2 rounded-md bg-fg text-sm font-medium text-bg shadow-xs transition-opacity hover:opacity-85"
        >
          Sign in with Discord
          <ArrowRight className="size-4" />
        </a>
      </div>
    </div>
  );
}
