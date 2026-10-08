import {
  Activity,
  BellRing,
  Bot,
  Boxes,
  ChevronsUpDown,
  Cpu,
  Database,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  Monitor,
  Moon,
  Settings,
  ShieldCheck,
  Sun,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router';
import { tokens } from '../lib/auth';
import { useAccentColor } from '../lib/branding';
import { useCurrentOrg, useOrganizations } from '../lib/org';
import { useBranding, useSuperadmin } from '../lib/queries';
import { type Theme, useTheme } from '../lib/theme';
import { OrgMark } from './org-mark';
import { cx } from './ui';

const NAV = [
  { to: '', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: 'compute', label: 'Compute', icon: Cpu },
  { to: 'apps', label: 'Apps', icon: Boxes },
  { to: 'knowledge', label: 'Knowledge', icon: Database },
  { to: 'alerts', label: 'Alerts', icon: BellRing },
  { to: 'agents', label: 'Agents', icon: Bot },
  { to: 'tokens', label: 'Tokens', icon: KeyRound },
  { to: 'activity', label: 'Activity', icon: Activity },
  { to: 'settings', label: 'Settings', icon: Settings },
];

const THEMES: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'system', label: 'System theme', icon: Monitor },
  { value: 'light', label: 'Light theme', icon: Sun },
  { value: 'dark', label: 'Dark theme', icon: Moon },
];

function OrgSwitcher() {
  const { org, prefix } = useCurrentOrg();
  const { data } = useOrganizations();
  const branding = useBranding(prefix);
  const navigate = useNavigate();
  const name = org?.name ?? prefix;
  return (
    <label className="relative flex items-center gap-2.5 rounded-lg border border-line bg-panel p-2 text-sm shadow-xs transition-colors hover:bg-panel-2 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring">
      <OrgMark name={name} logoUrl={branding.data?.logo_url} className="size-8" />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{name}</span>
        <span className="block truncate font-mono text-xs text-muted">{prefix}</span>
      </span>
      <ChevronsUpDown className="size-4 shrink-0 text-muted" />
      <select
        aria-label="Organization"
        className="absolute inset-0 cursor-pointer opacity-0"
        value={prefix}
        onChange={(e) => navigate(`/${e.target.value}`)}
      >
        {data?.map((o) => (
          <option key={o.id} value={o.prefix}>
            {o.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function ThemeSwitch() {
  const [theme, setTheme] = useTheme();
  return (
    <div role="radiogroup" aria-label="Theme" className="flex items-center gap-0.5 rounded-full border border-line p-0.5">
      {THEMES.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={theme === value}
          aria-label={label}
          title={label}
          onClick={() => setTheme(value)}
          className={cx(
            'flex size-6 cursor-pointer items-center justify-center rounded-full transition-colors',
            theme === value ? 'bg-panel-2 text-fg' : 'text-muted hover:text-fg',
          )}
        >
          <Icon className="size-3.5" />
        </button>
      ))}
    </div>
  );
}

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  const { prefix } = useCurrentOrg();
  const navigate = useNavigate();
  const { data: superadmin } = useSuperadmin();
  const items = superadmin ? [...NAV, { to: 'admin', label: 'Superadmin', icon: ShieldCheck, end: false }] : NAV;
  return (
    <div className="flex h-full flex-col gap-5 p-3">
      <OrgSwitcher />
      <nav aria-label="Pages" className="flex flex-col gap-0.5">
        {items.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={label}
            to={`/${prefix}${to ? `/${to}` : ''}`}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cx(
                'flex h-8 items-center gap-2.5 rounded-md px-2.5 text-sm transition-colors',
                isActive ? 'bg-panel-2 font-medium text-fg' : 'text-muted hover:bg-panel-2/60 hover:text-fg',
              )
            }
          >
            <Icon className="size-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto flex items-center justify-between gap-2 border-t border-line pt-3">
        <button
          className="flex h-8 cursor-pointer items-center gap-2 rounded-md px-2.5 text-sm text-muted transition-colors hover:bg-panel-2/60 hover:text-fg"
          onClick={() => {
            tokens.clear();
            navigate('/login');
          }}
        >
          <LogOut className="size-4" />
          Sign out
        </button>
        <ThemeSwitch />
      </div>
    </div>
  );
}

export function Shell() {
  const [open, setOpen] = useState(false);
  const { org, prefix } = useCurrentOrg();
  const branding = useBranding(prefix);
  useAccentColor(branding.data?.accent_color);
  const name = org?.name ?? prefix;
  return (
    <div className="min-h-screen md:grid md:grid-cols-[248px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-screen border-r border-line md:block">
        <Nav />
      </aside>
      <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-bg/80 px-4 backdrop-blur md:hidden">
        <button
          aria-label="Open menu"
          className="-ml-1.5 flex size-8 cursor-pointer items-center justify-center rounded-md hover:bg-panel-2"
          onClick={() => setOpen(true)}
        >
          <Menu className="size-5" />
        </button>
        <span className="flex min-w-0 items-center gap-2 text-sm font-medium">
          <OrgMark name={name} logoUrl={branding.data?.logo_url} />
          <span className="truncate">{name}</span>
        </span>
      </header>
      {open ? (
        <div className="fixed inset-0 z-30 md:hidden">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px]" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-line bg-bg shadow-xl">
            <button
              aria-label="Close menu"
              className="absolute top-3.5 right-3 flex size-8 cursor-pointer items-center justify-center rounded-md hover:bg-panel-2"
              onClick={() => setOpen(false)}
            >
              <X className="size-4" />
            </button>
            <div className="h-full pt-12">
              <Nav onNavigate={() => setOpen(false)} />
            </div>
          </aside>
        </div>
      ) : null}
      <main className="mx-auto w-full max-w-6xl min-w-0 px-4 py-8 sm:px-6 md:py-10 lg:px-10">
        <Outlet />
      </main>
    </div>
  );
}
