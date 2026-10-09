import { ArrowUpRight, BookOpen, Info } from 'lucide-react';
import type { ReactNode } from 'react';
import { ABOUT_URL, builtByLabel, DOCS_URL, SOURCE_URL } from '../lib/links';
import { GitHubIcon } from './brand-icons';
import { Logo } from './logo';
import { OrgMarks } from './built-by';

const LINKS = [
  { label: 'Docs', href: DOCS_URL, icon: BookOpen },
  { label: 'GitHub', href: SOURCE_URL, icon: GitHubIcon },
  { label: 'What is this?', href: ABOUT_URL, icon: Info },
];

// The frame of the pages before the dashboard: sign-in, the sign-in return and the org list.
// It shows the Platform mark at the top, and the orgs that build Platform and the help links at the bottom.
export function AuthFrame({ children, width = 'max-w-sm' }: { children: ReactNode; width?: string }) {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden">
      <div className="grid-bg pointer-events-none absolute inset-0" aria-hidden />
      <header className="relative flex h-14 items-center px-4 sm:px-6">
        <a href={ABOUT_URL} className="flex items-center gap-2 rounded-md text-sm font-semibold tracking-tight">
          <Logo className="size-5" />
          Platform
        </a>
      </header>
      <main className="relative flex flex-1 flex-col items-center justify-center px-4 py-10">
        <div className={`w-full ${width} animate-in`}>{children}</div>
      </main>
      <footer className="relative flex flex-col items-center gap-4 px-4 pt-6 pb-8">
        <div className="flex items-center gap-2.5 text-xs text-muted">
          <OrgMarks size={24} />
          <span>{builtByLabel()}</span>
        </div>
        <nav aria-label="Help" className="flex flex-wrap items-center justify-center gap-x-1 gap-y-1 text-xs">
          {LINKS.map(({ label, href, icon: Icon }) => (
            <a
              key={label}
              href={href}
              target="_blank"
              rel="noreferrer"
              className="group flex h-7 items-center gap-1.5 rounded-md px-2 text-muted transition-colors hover:bg-panel-2 hover:text-fg"
            >
              <Icon className="size-3.5" />
              {label}
              <ArrowUpRight className="size-3 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden />
            </a>
          ))}
        </nav>
      </footer>
    </div>
  );
}
