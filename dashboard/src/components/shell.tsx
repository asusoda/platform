import { useQueryClient } from '@tanstack/react-query';
import {
  ChevronsUpDown,
  Globe,
  LogOut,
  Menu,
  Monitor,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldCheck,
  Sun,
  X,
} from 'lucide-react';
import { type ComponentType, type ReactNode, useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router';
import { useAccentColor } from '../lib/branding';
import { useCurrentOrg, useOrganizations } from '../lib/org';
import { useBranding, useModules, useSuperadmin } from '../lib/queries';
import { useSignOut } from '../lib/query-client';
import { useSidebarCollapsed } from '../lib/sidebar';
import { type Theme, useTheme } from '../lib/theme';
import { type PageEntry, PAGES, SECTIONS } from '../pages/registry';
import { NotificationsBell } from './notifications';
import { OrgMark } from './org-mark';
import { MOD_KEY, Tooltip } from './tooltip';
import { cx, type PageMeta, PageMetaProvider } from './ui';

// The path of the superadmin space. The org switcher offers it to the superadmin.
export const ADMIN_PATH = '/admin';

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
const iconButton =
  'flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-md text-muted transition-colors duration-150 hover:bg-panel-2 hover:text-fg';

// What the sidebar parts get: whether the sidebar is a rail, and what to do after a link opens a page.
export type SidebarState = { collapsed: boolean; onNavigate?: () => void };

// The page entry for the current URL, /<space>/<path>, from a list of pages.
export function useCurrentEntry<T extends { path: string }>(pages: T[]): T | undefined {
  const { pathname } = useLocation();
  const path = pathname.split('/')[2] ?? '';
  return pages.find((p) => p.path === path);
}

// The mark of the superadmin space, in the size of an org mark.
export function AdminMark({ className }: { className?: string }) {
  return (
    <span aria-hidden className={cx('flex shrink-0 items-center justify-center rounded-md bg-fg text-bg', className ?? 'size-6')}>
      <ShieldCheck className="size-[60%]" />
    </span>
  );
}

// The box at the top of the sidebar: the current space and a select that opens another one.
export function Switcher({
  collapsed,
  name,
  sub,
  mark,
  value,
  options,
  onPick,
}: {
  collapsed: boolean;
  name: string;
  sub: string;
  mark: ReactNode;
  value: string;
  options: { value: string; label: string }[];
  onPick: (value: string) => void;
}) {
  return (
    <Tooltip label={name} disabled={!collapsed}>
      <label
        className={cx(
          'relative flex h-10 shrink-0 items-center gap-2.5 overflow-hidden rounded-lg border p-[5px] text-sm transition-[background-color,border-color,box-shadow] duration-150 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring',
          collapsed ? 'w-10 border-transparent hover:bg-panel-2/70' : 'w-full border-line bg-panel shadow-xs hover:bg-panel-2',
        )}
      >
        {mark}
        <span className={cx('min-w-0 flex-1 leading-tight', labelClass(collapsed))}>
          <span className="block truncate font-medium">{name}</span>
          <span className="block truncate font-mono text-[11px] text-muted">{sub}</span>
        </span>
        <ChevronsUpDown className="mr-1 size-4 shrink-0 text-muted" />
        <select
          aria-label="Organization"
          className="absolute inset-0 cursor-pointer opacity-0"
          value={value}
          onChange={(e) => onPick(e.target.value)}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
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
  onPrefetch,
}: {
  to: string;
  end?: boolean;
  label: string;
  icon: ComponentType<{ className?: string }>;
  collapsed: boolean;
  onNavigate?: () => void;
  onPrefetch?: () => void;
}) {
  return (
    <Tooltip label={label} disabled={!collapsed}>
      <NavLink
        to={to}
        end={end}
        onClick={onNavigate}
        onMouseEnter={onPrefetch}
        onFocus={onPrefetch}
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

export type NavLinkItem = { to: string; end?: boolean; label: string; icon: ComponentType<{ className?: string }>; onPrefetch?: () => void };
export type NavSection = { id: string; title?: string; items: NavLinkItem[] };

// The page links of the sidebar, in sections. The first section has no header.
export function SidebarNav({ sections, collapsed, onNavigate }: SidebarState & { sections: NavSection[] }) {
  return (
    <nav aria-label="Pages" className="flex flex-col">
      {sections
        .filter((s) => s.items.length)
        .map((section, i) => (
          <div key={section.id} role="group" aria-label={section.title} className="flex flex-col gap-0.5">
            {i ? <SectionSlot title={section.title} collapsed={collapsed} /> : null}
            {section.items.map((item) => (
              <NavItem key={item.to} {...item} collapsed={collapsed} onNavigate={onNavigate} />
            ))}
          </div>
        ))}
    </nav>
  );
}

function SidebarFooter({ collapsed }: { collapsed: boolean }) {
  const signOut = useSignOut();
  return (
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
        <div className="flex items-center justify-between gap-2">
          <button type="button" onClick={signOut} className={cx(itemClass, quietItem, 'cursor-pointer')}>
            <LogOut className="size-4 shrink-0" />
            Sign out
          </button>
          <ThemeSwitch />
        </div>
      )}
    </div>
  );
}

// One crumb of the top bar after the first, with a slash before it.
export function Crumb({ children, current, className }: { children: ReactNode; current?: boolean; className?: string }) {
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

// The first crumb: the mark and name of the space, as a link to its home page.
export function HomeCrumb({ to, mark, name }: { to: string; mark: ReactNode; name: string }) {
  return (
    <li className="flex min-w-0 items-center">
      <Link to={to} className="flex min-w-0 items-center gap-2 rounded-md px-1 py-0.5 text-muted transition-colors hover:text-fg">
        {mark}
        <span className="truncate">{name}</span>
      </Link>
    </li>
  );
}

// The frame of a space: the sidebar (or the drawer on a phone), the top bar with the crumbs, and the page.
// header and nav fill the sidebar; the footer with sign out and the theme is the same in every space. page is the
// registry entry of the current page, which PageHeader reads.
export function Frame({
  header,
  nav,
  crumbs,
  actions,
  page,
}: {
  header: (state: SidebarState) => ReactNode;
  nav: (state: SidebarState) => ReactNode;
  crumbs: ReactNode;
  actions?: ReactNode;
  page?: PageMeta;
}) {
  const [drawer, setDrawer] = useState(false);
  const [collapsed, toggle] = useSidebarCollapsed();
  const { pathname } = useLocation();

  useEffect(() => setDrawer(false), [pathname]);
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setDrawer(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [drawer]);

  const sidebar = (state: SidebarState, className: string) => (
    <div className={cx('flex h-full flex-col', className)}>
      <div className="p-2">{header(state)}</div>
      <div className="flex min-h-0 flex-1 flex-col overflow-x-hidden overflow-y-auto px-2 pb-2 [scrollbar-width:thin]">{nav(state)}</div>
      <SidebarFooter collapsed={state.collapsed} />
    </div>
  );

  return (
    <div className="shell min-h-screen" data-collapsed={collapsed || undefined}>
      <aside aria-label="Sidebar" className="sticky top-0 hidden h-screen overflow-hidden border-r border-line md:block">
        {sidebar({ collapsed }, 'w-[248px]')}
      </aside>
      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-20 flex h-12 items-center gap-2 border-b border-line bg-bg/85 px-3 backdrop-blur-md sm:px-4">
          <button type="button" aria-label="Open menu" className={cx(iconButton, 'md:hidden')} onClick={() => setDrawer(true)}>
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
                onClick={toggle}
              >
                {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
              </button>
            </Tooltip>
          </span>
          <span aria-hidden className="mx-1 h-4 w-px bg-line-strong" />
          <nav aria-label="Breadcrumb" className="min-w-0 flex-1">
            <ol className="flex min-w-0 items-center gap-1.5 text-sm">{crumbs}</ol>
          </nav>
          {actions}
        </header>
        <main className="mx-auto w-full max-w-6xl min-w-0 px-4 pt-8 pb-16 sm:px-6 lg:px-10">
          <PageMetaProvider value={page}>
            <Outlet />
          </PageMetaProvider>
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
          <div className="h-full pt-11">{sidebar({ collapsed: false, onNavigate: () => setDrawer(false) }, 'w-full')}</div>
        </aside>
      </div>
    </div>
  );
}

function OrgSwitcher({ collapsed }: SidebarState) {
  const { org, prefix } = useCurrentOrg();
  const { data } = useOrganizations();
  const { data: superadmin } = useSuperadmin();
  const branding = useBranding(prefix);
  const navigate = useNavigate();
  const name = org?.name ?? prefix;
  const options = (data ?? []).map((o) => ({ value: o.prefix, label: o.name }));
  if (superadmin) options.push({ value: ADMIN_PATH, label: 'Superadmin' });
  return (
    <Switcher
      collapsed={collapsed}
      name={name}
      sub={prefix}
      mark={<OrgMark name={name} logoUrl={branding.data?.logo_url} className="size-7" />}
      value={prefix}
      options={options}
      onPick={(value) => navigate(value === ADMIN_PATH ? ADMIN_PATH : `/${value}`)}
    />
  );
}

function OrgNav({ collapsed, onNavigate }: SidebarState) {
  const { org, prefix } = useCurrentOrg();
  const client = useQueryClient();
  const modules = useModules(org?.id).data?.modules;
  const website = useBranding(prefix).data?.website_url;
  // A module is hidden only when the API says it is off. A page with a list of modules is hidden when all are off.
  const off = (name: string) => modules?.some((m) => m.name === name && !m.enabled) ?? false;
  const shown = (page: PageEntry) => !page.hidden && !(page.module && [page.module].flat().every(off));
  const sections = SECTIONS.map((s) => ({
    id: s.id,
    title: 'title' in s ? s.title : undefined,
    items: PAGES.filter((p) => p.section === s.id && shown(p)).map(({ path, label, icon, prefetch }) => ({
      to: `/${prefix}${path ? `/${path}` : ''}`,
      end: !path,
      label,
      icon,
      onPrefetch: prefetch && prefix ? () => prefetch(client, prefix) : undefined,
    })),
  }));
  return (
    <>
      <SidebarNav sections={sections} collapsed={collapsed} onNavigate={onNavigate} />
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
    </>
  );
}

// A link to the superadmin space in the top bar of an org, for the superadmin only.
function AdminLink() {
  const { data: superadmin } = useSuperadmin();
  if (!superadmin) return null;
  return (
    <Tooltip label="Superadmin" side="bottom">
      <Link
        to={ADMIN_PATH}
        aria-label="Superadmin"
        className="flex h-8 shrink-0 items-center gap-1.5 rounded-md px-2 text-xs font-medium text-muted transition-colors hover:bg-panel-2 hover:text-fg"
      >
        <ShieldCheck className="size-4" />
        <span className="hidden sm:inline">Superadmin</span>
      </Link>
    </Tooltip>
  );
}

// The shell of an org: its pages from pages/registry.tsx, as Org / Section / Page.
export function Shell() {
  const { org, prefix } = useCurrentOrg();
  const branding = useBranding(prefix);
  const page = useCurrentEntry(PAGES);
  const client = useQueryClient();
  useAccentColor(branding.data?.accent_color);
  const name = org?.name ?? prefix;
  const section = SECTIONS.find((s) => s.id === page?.section);
  const sectionTitle = section && 'title' in section ? section.title : undefined;

  // The page requests start with the org list, not after the module check of a gated page.
  useEffect(() => {
    if (page?.prefetch && prefix) page.prefetch(client, prefix);
  }, [client, page, prefix]);

  useEffect(() => {
    document.title = page ? `${page.label} - ${name} - Platform` : 'Platform';
  }, [page, name]);

  return (
    <Frame
      page={page}
      header={(state) => <OrgSwitcher {...state} />}
      nav={(state) => <OrgNav {...state} />}
      crumbs={
        <>
          <HomeCrumb to={`/${prefix}`} mark={<OrgMark name={name} logoUrl={branding.data?.logo_url} className="size-5" />} name={name} />
          {sectionTitle ? <Crumb className="hidden sm:flex">{sectionTitle}</Crumb> : null}
          {page ? <Crumb current>{page.label}</Crumb> : null}
        </>
      }
      actions={
        <>
          <AdminLink />
          <NotificationsBell />
        </>
      }
    />
  );
}
