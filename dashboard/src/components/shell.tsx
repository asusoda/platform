import { ChevronsUpDown, Globe, LogOut, Menu, Monitor, Moon, PanelLeftClose, PanelLeftOpen, Sun, X } from 'lucide-react';
import { type ComponentType, type ReactNode, useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router';
import { tokens } from '../lib/auth';
import { useAccentColor } from '../lib/branding';
import { builtByLabel } from '../lib/links';
import { useCurrentOrg, useOrganizations } from '../lib/org';
import { useBranding, useModules, useSuperadmin } from '../lib/queries';
import { useSidebarCollapsed } from '../lib/sidebar';
import { type Theme, useTheme } from '../lib/theme';
import { type PageEntry, PAGES, SECTIONS } from '../pages/registry';
import { NotificationsBell } from './notifications';
import { OrgMark } from './org-mark';
import { OrgMarks } from './built-by';
import { MOD_KEY, Tooltip } from './tooltip';
import { cx } from './ui';

const THEMES: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'system', label: 'System theme', icon: Monitor },
  { value: 'light', label: 'Light theme', icon: Sun },
  { value: 'dark', label: 'Dark theme', icon: Moon },
];

// The sidebar content is always 248px wide. The rail shows its first 56px: each row starts with a 40px icon box.
const itemClass =
  'flex h-8 shrink-0 items-center gap-2.5 overflow-hidden rounded-md px-3 text-sm whitespace-nowrap transition-colors duration-150';
const quietItem = 'text-muted hover:bg-panel-2/70 hover:text-fg';
const labelClass = (collapsed: boolean) => cx('truncate transition-opacity duration-150', collapsed && 'opacity-0');

// The page entry for the current URL: /<org>/<path>.
function useCurrentPage(): PageEntry | undefined {
  const { pathname } = useLocation();
  const path = pathname.split('/')[2] ?? '';
  return PAGES.find((p) => p.path === path);
}

function OrgSwitcher({ collapsed }: { collapsed: boolean }) {
  const { org, prefix } = useCurrentOrg();
  const { data } = useOrganizations();
  const branding = useBranding(prefix);
  const navigate = useNavigate();
  const name = org?.name ?? prefix;
  return (
    <Tooltip label={name} disabled={!collapsed}>
      <label
        className={cx(
          'relative flex h-10 shrink-0 items-center gap-2.5 overflow-hidden rounded-lg border p-[5px] text-sm transition-[background-color,border-color,box-shadow] duration-150 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring',
          collapsed ? 'w-10 border-transparent hover:bg-panel-2/70' : 'w-full border-line bg-panel shadow-xs hover:bg-panel-2',
        )}
      >
        <OrgMark name={name} logoUrl={branding.data?.logo_url} className="size-7" />
        <span className={cx('min-w-0 flex-1 leading-tight', labelClass(collapsed))}>
          <span className="block truncate font-medium">{name}</span>
          <span className="block truncate font-mono text-[11px] text-muted">{prefix}</span>
        </span>
        <ChevronsUpDown className="mr-1 size-4 shrink-0 text-muted" />
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
    </Tooltip>
  );
}

function ThemeSwitch() {
  const [theme, setTheme] = useTheme();
  return (
    <div role="radiogroup" aria-label="Theme" className="flex items-center gap-0.5 rounded-full border border-line p-0.5">
      {THEMES.map(({ value, label, icon: Icon }) => (
        <Tooltip key={value} label={label} side="top">
          <button
            type="button"
            role="radio"
            aria-checked={theme === value}
            aria-label={label}
            onClick={() => setTheme(value)}
            className={cx(
              'flex size-6 cursor-pointer items-center justify-center rounded-full transition-colors duration-150',
              theme === value ? 'bg-panel-2 text-fg shadow-xs' : 'text-muted hover:text-fg',
            )}
          >
            <Icon className="size-3.5" />
          </button>
        </Tooltip>
      ))}
    </div>
  );
}

// One button that moves to the next theme, for the rail.
function ThemeCycle() {
  const [theme, setTheme] = useTheme();
  const i = THEMES.findIndex((t) => t.value === theme);
  const { label, icon: Icon } = THEMES[i];
  const next = THEMES[(i + 1) % THEMES.length];
  return (
    <Tooltip label={`${label}. Select for ${next.label.toLowerCase()}`}>
      <button type="button" aria-label={`${label}. Change theme`} onClick={() => setTheme(next.value)} className={cx(itemClass, quietItem, 'w-10 cursor-pointer')}>
        <Icon className="size-4 shrink-0" />
      </button>
    </Tooltip>
  );
}

function SectionSlot({ title, collapsed }: { title?: string; collapsed: boolean }) {
  return (
    <div className={cx('relative shrink-0', title ? 'h-8' : 'h-3')}>
      {title ? (
        <h2
          className={cx(
            'absolute bottom-1 left-3 text-[11px] font-medium tracking-wide whitespace-nowrap text-muted/80 uppercase transition-opacity duration-150',
            collapsed && 'opacity-0',
          )}
        >
          {title}
        </h2>
      ) : null}
      <span
        aria-hidden
        className={cx(
          'absolute top-1/2 left-2 h-px w-6 bg-line-strong transition-opacity duration-150',
          collapsed ? 'opacity-100' : 'opacity-0',
        )}
      />
    </div>
  );
}

function NavItem({
  to,
  end,
  label,
  icon: Icon,
  collapsed,
  onNavigate,
}: {
  to: string;
  end?: boolean;
  label: string;
  icon: ComponentType<{ className?: string }>;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  return (
    <Tooltip label={label} disabled={!collapsed}>
      <NavLink
        to={to}
        end={end}
        onClick={onNavigate}
        aria-label={collapsed ? label : undefined}
        className={({ isActive }) =>
          cx(itemClass, collapsed ? 'w-10' : 'w-full', isActive ? 'bg-panel-2 font-medium text-fg' : quietItem)
        }
      >
        <Icon className="size-4 shrink-0" />
        <span className={labelClass(collapsed)}>{label}</span>
      </NavLink>
    </Tooltip>
  );
}

function Nav({ collapsed = false, onNavigate, className = 'w-[248px]' }: { collapsed?: boolean; onNavigate?: () => void; className?: string }) {
  const { org, prefix } = useCurrentOrg();
  const navigate = useNavigate();
  const { data: superadmin } = useSuperadmin();
  const modules = useModules(org?.id).data?.modules;
  const website = useBranding(prefix).data?.website_url;
  // A module is hidden only when the API says it is off.
  const shown = (page: PageEntry) =>
    (!page.superadmin || superadmin) && !(page.module && modules?.some((m) => m.name === page.module && !m.enabled));
  const sections = SECTIONS.map((s) => ({
    id: s.id,
    title: 'title' in s ? s.title : undefined,
    items: PAGES.filter((p) => p.section === s.id && shown(p)),
  })).filter((s) => s.items.length);
  const signOut = () => {
    tokens.clear();
    navigate('/login');
  };
  return (
    <div className={cx('flex h-full flex-col', className)}>
      <div className="p-2">
        <OrgSwitcher collapsed={collapsed} />
      </div>
      <div className="flex min-h-0 flex-1 flex-col overflow-x-hidden overflow-y-auto px-2 pb-2 [scrollbar-width:thin]">
        <nav aria-label="Pages" className="flex flex-col">
          {sections.map((section, i) => (
            <div key={section.id} role="group" aria-label={section.title} className="flex flex-col gap-0.5">
              {i ? <SectionSlot title={section.title} collapsed={collapsed} /> : null}
              {section.items.map(({ path, label, icon }) => (
                <NavItem
                  key={label}
                  to={`/${prefix}${path ? `/${path}` : ''}`}
                  end={!path}
                  label={label}
                  icon={icon}
                  collapsed={collapsed}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          ))}
        </nav>
        {website ? (
          <div className="mt-3 flex flex-col">
            <Tooltip label={new URL(website).host} disabled={!collapsed}>
              <a
                href={website}
                target="_blank"
                rel="noreferrer"
                aria-label={collapsed ? `Website: ${new URL(website).host}` : undefined}
                className={cx(itemClass, quietItem, collapsed ? 'w-10' : 'w-full')}
              >
                <Globe className="size-4 shrink-0" />
                <span className={labelClass(collapsed)}>{new URL(website).host}</span>
              </a>
            </Tooltip>
          </div>
        ) : null}
      </div>
      <div className="border-t border-line p-2">
        {collapsed ? (
          <div className="flex flex-col gap-0.5">
            <ThemeCycle />
            <Tooltip label="Sign out">
              <button type="button" aria-label="Sign out" onClick={signOut} className={cx(itemClass, quietItem, 'w-10 cursor-pointer')}>
                <LogOut className="size-4 shrink-0" />
              </button>
            </Tooltip>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2">
              <button type="button" onClick={signOut} className={cx(itemClass, quietItem, 'cursor-pointer')}>
                <LogOut className="size-4 shrink-0" />
                Sign out
              </button>
              <ThemeSwitch />
            </div>
            <div className="flex items-center gap-2.5 px-3 pt-1 pb-0.5">
              <OrgMarks size={20} />
              <span className="truncate text-[11px] text-muted">{builtByLabel(undefined, true)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// The bar above each page: the sidebar button and where the page is, as Org / Section / Page.
function TopBar({ collapsed, onToggle, onMenu }: { collapsed: boolean; onToggle: () => void; onMenu: () => void }) {
  const { org, prefix } = useCurrentOrg();
  const branding = useBranding(prefix);
  const page = useCurrentPage();
  const name = org?.name ?? prefix;
  const section = SECTIONS.find((s) => s.id === page?.section);
  const sectionTitle = section && 'title' in section ? section.title : undefined;
  const iconButton =
    'flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-md text-muted transition-colors duration-150 hover:bg-panel-2 hover:text-fg';
  return (
    <header className="sticky top-0 z-20 flex h-12 items-center gap-2 border-b border-line bg-bg/85 px-3 backdrop-blur-md sm:px-4">
      <button type="button" aria-label="Open menu" className={cx(iconButton, 'md:hidden')} onClick={onMenu}>
        <Menu className="size-[18px]" />
      </button>
      <span className="hidden md:contents">
        <Tooltip label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} keys={[MOD_KEY, 'B']} side="bottom">
          <button
            type="button"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-keyshortcuts="Control+B Meta+B ["
            aria-expanded={!collapsed}
            className={iconButton}
            onClick={onToggle}
          >
            {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
          </button>
        </Tooltip>
      </span>
      <span aria-hidden className="mx-1 h-4 w-px bg-line-strong" />
      <nav aria-label="Breadcrumb" className="min-w-0 flex-1">
        <ol className="flex min-w-0 items-center gap-1.5 text-sm">
          <li className="flex min-w-0 items-center">
            <Link to={`/${prefix}`} className="flex min-w-0 items-center gap-2 rounded-md px-1 py-0.5 text-muted transition-colors hover:text-fg">
              <OrgMark name={name} logoUrl={branding.data?.logo_url} className="size-5" />
              <span className="truncate">{name}</span>
            </Link>
          </li>
          {sectionTitle ? <Crumb className="hidden sm:flex">{sectionTitle}</Crumb> : null}
          {page ? <Crumb current>{page.label}</Crumb> : null}
        </ol>
      </nav>
      <NotificationsBell />
    </header>
  );
}

function Crumb({ children, current, className }: { children: ReactNode; current?: boolean; className?: string }) {
  return (
    <li className={cx('flex min-w-0 items-center gap-1.5', className)}>
      <span aria-hidden className="text-muted/50">
        /
      </span>
      <span aria-current={current ? 'page' : undefined} className={cx('truncate', current ? 'font-medium text-fg' : 'text-muted')}>
        {children}
      </span>
    </li>
  );
}

export function Shell() {
  const [drawer, setDrawer] = useState(false);
  const [collapsed, toggle] = useSidebarCollapsed();
  const { org, prefix } = useCurrentOrg();
  const branding = useBranding(prefix);
  const page = useCurrentPage();
  const { pathname } = useLocation();
  useAccentColor(branding.data?.accent_color);
  const name = org?.name ?? prefix;

  useEffect(() => {
    document.title = page ? `${page.label} - ${name} - Platform` : 'Platform';
  }, [page, name]);
  useEffect(() => setDrawer(false), [pathname]);
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setDrawer(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [drawer]);

  return (
    <div className="shell min-h-screen" data-collapsed={collapsed || undefined}>
      <aside aria-label="Sidebar" className="sticky top-0 hidden h-screen overflow-hidden border-r border-line md:block">
        <Nav collapsed={collapsed} />
      </aside>
      <div className="flex min-w-0 flex-col">
        <TopBar collapsed={collapsed} onToggle={toggle} onMenu={() => setDrawer(true)} />
        <main className="mx-auto w-full max-w-6xl min-w-0 px-4 pt-8 pb-16 sm:px-6 lg:px-10">
          <Outlet />
        </main>
      </div>
      <div className={cx('fixed inset-0 z-30 md:hidden', !drawer && 'pointer-events-none')} inert={!drawer}>
        <div
          className={cx('absolute inset-0 bg-black/40 backdrop-blur-[2px] transition-opacity duration-200', drawer ? 'opacity-100' : 'opacity-0')}
          onClick={() => setDrawer(false)}
        />
        <aside
          aria-label="Menu"
          className={cx(
            'absolute inset-y-0 left-0 w-[264px] max-w-[85vw] overflow-hidden border-r border-line bg-bg shadow-xl transition-transform duration-200 ease-out',
            drawer ? 'translate-x-0' : '-translate-x-full',
          )}
        >
          <button
            aria-label="Close menu"
            className="absolute top-2.5 right-2 z-10 flex size-8 cursor-pointer items-center justify-center rounded-md text-muted hover:bg-panel-2 hover:text-fg"
            onClick={() => setDrawer(false)}
          >
            <X className="size-4" />
          </button>
          <div className="h-full pt-11">
            <Nav onNavigate={() => setDrawer(false)} className="w-full" />
          </div>
        </aside>
      </div>
    </div>
  );
}
