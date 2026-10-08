import { useSearchParams } from 'react-router';
import { loginUrl } from '../lib/api';
import { Card, ErrorNote } from '../components/ui';

export function LoginPage() {
  const [params] = useSearchParams();
  const error = params.get('error');
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm p-6">
        <svg viewBox="0 0 24 24" className="size-8" aria-hidden>
          <rect x="3" y="4" width="18" height="4" rx="2" className="fill-fg" />
          <rect x="3" y="10" width="18" height="4" rx="2" className="fill-muted" />
          <rect x="3" y="16" width="18" height="4" rx="2" className="fill-line" />
        </svg>
        <h1 className="mt-4 text-lg font-semibold">Platform dashboard</h1>
        <p className="mt-1 text-sm text-muted">Sign in with the Discord account that holds your organization's officer role.</p>
        {error ? (
          <div className="mt-4">
            <ErrorNote error={error} />
          </div>
        ) : null}
        <a
          href={loginUrl()}
          className="mt-6 flex h-10 items-center justify-center rounded-lg bg-[#5865F2] text-sm font-medium text-white hover:opacity-90"
        >
          Sign in with Discord
        </a>
      </Card>
    </div>
  );
}
