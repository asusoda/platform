import { CircleAlert } from 'lucide-react';
import { useSearchParams } from 'react-router';
import { AuthFrame } from '../components/auth-frame';
import { DiscordIcon } from '../components/brand-icons';
import { Logo } from '../components/logo';
import { loginUrl } from '../lib/api';

export function LoginPage() {
  const [params] = useSearchParams();
  const error = params.get('error');
  return (
    <AuthFrame>
      <div className="rounded-2xl border border-line bg-panel p-6 shadow-xs sm:p-8">
        <span className="flex size-10 items-center justify-center rounded-xl border border-line bg-bg">
          <Logo className="size-5" />
        </span>
        <h1 className="mt-5 text-xl font-semibold tracking-tight">Sign in to Platform</h1>
        <p className="mt-1.5 text-sm text-pretty text-muted">Infrastructure for student organizations.</p>
        {error ? (
          <div role="alert" className="mt-5 flex animate-in gap-2.5 rounded-lg border border-bad/30 bg-bad/10 p-3 text-sm">
            <CircleAlert className="mt-0.5 size-4 shrink-0 text-bad" />
            <div className="min-w-0">
              <p className="font-medium text-bad">Sign-in did not work</p>
              <p className="mt-0.5 text-pretty break-words text-fg/80">{error}</p>
              <p className="mt-1.5 text-xs text-muted">Try again. If it fails again, ask an officer of your org to check your role.</p>
            </div>
          </div>
        ) : null}
        <a
          href={loginUrl()}
          className="mt-6 flex h-10 items-center justify-center gap-2.5 rounded-lg bg-fg text-sm font-medium text-bg shadow-xs transition-[opacity,scale] duration-150 select-none hover:opacity-90 active:scale-[0.98]"
        >
          <DiscordIcon className="size-[18px]" />
          {error ? 'Try again with Discord' : 'Continue with Discord'}
        </a>
        <p className="mt-4 text-xs text-pretty text-muted">
          Use the Discord account that has the officer role in your org's server.
        </p>
      </div>
    </AuthFrame>
  );
}
