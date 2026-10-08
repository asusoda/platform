import {
  Activity,
  BellRing,
  Bot,
  Boxes,
  ChevronsUpDown,
  Cpu,
  GitBranch,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router';
import { tokens } from '../lib/auth';
import { useCurrentOrg, useOrganizations } from '../lib/org';
import { cx } from './ui';

const NAV = [
  { to: '', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: 'compute', label: 'Compute', icon: Cpu },
  { to: 'alerts', label: 'Alerts', icon: BellRing },
  { to: 'apps', label: 'Apps and knowledge', icon: Boxes },
  { to: 'agents', label: 'Agents', icon: Bot },
  { to: 'ci', label: 'CI runs', icon: GitBranch },
  { to: 'tokens', label: 'Tokens', icon: KeyRound },
  { to: 'activity', label: 'Activity', icon: Activity },
  { to: 'settings', label: 'Settings', icon: Settings },
];

function Logo() {
  return (
    <svg viewBox="0 0 24 24" className="size-5" aria-hidden>
      <rect x="3" y="4" width="18" height="4" rx="2" className="fill-fg" />
      <rect x="3" y="10" width="18" height="4" rx="2" className="fill-muted" />
      <rect x="3" y="16" width="18" height="4" rx="2" className="fill-line" />
    </svg>
  );
}

function OrgSwitcher() {
  const { org, prefix } = useCurrentOrg();
  const { data } = useOrganizations();
  const navigate = useNavigate();
  return (
    <label className="relative flex h-10 items-center gap-2 rounded-lg border border-line bg-panel-2 px-3 text-sm">
      <span className="flex size-5 items-center justify-center rounded bg-fg text-[10px] font-semibold text-bg uppercase">
        {(org?.name ?? prefix).slice(0, 1)}
      </span>
      <span className="min-w-0 flex-1 truncate">{org?.name ?? prefix}</span>
      <ChevronsUpDown className="size-4 text-muted" />
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

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  const { prefix } = useCurrentOrg();
  const navigate = useNavigate();
  return (
    <div className="flex h-full flex-col gap-4 p-3">
      <div className="flex items-center gap-2 px-2 pt-1 font-semibold">
        <Logo />
        Platform
      </div>
      <OrgSwitcher />
      <nav className="flex flex-col gap-0.5">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={label}
            to={`/${prefix}${to ? `/${to}` : ''}`}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cx(
                'flex h-8 items-center gap-2.5 rounded-lg px-2.5 text-sm transition',
                isActive ? 'bg-panel-2 font-medium text-fg' : 'text-muted hover:bg-panel-2 hover:text-fg',
              )
            }
          >
            <Icon className="size-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <button
        className="mt-auto flex h-8 items-center gap-2.5 rounded-lg px-2.5 text-sm text-muted hover:bg-panel-2 hover:text-fg"
        onClick={() => {
          tokens.clear();
          navigate('/login');
        }}
      >
        <LogOut className="size-4" />
        Sign out
      </button>
    </div>
  );
}

export function Shell() {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_1fr]">
      <aside className="sticky top-0 hidden h-screen border-r border-line bg-panel md:block">
        <Nav />
      </aside>
      <header className="sticky top-0 z-20 flex h-12 items-center gap-3 border-b border-line bg-panel/90 px-4 backdrop-blur md:hidden">
        <button aria-label="Open menu" onClick={() => setOpen(true)}>
          <Menu className="size-5" />
        </button>
        <span className="flex items-center gap-2 font-semibold">
          <Logo /> Platform
        </span>
      </header>
      {open ? (
        <div className="fixed inset-0 z-30 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-line bg-panel">
            <button aria-label="Close menu" className="absolute top-3 right-3" onClick={() => setOpen(false)}>
              <X className="size-5" />
            </button>
            <Nav onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      ) : null}
      <main className="mx-auto w-full max-w-6xl px-4 py-6 md:px-8 md:py-8">
        <Outlet />
      </main>
    </div>
  );
}
