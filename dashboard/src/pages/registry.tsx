import {
  Activity,
  Bell,
  Blocks,
  BellRing,
  Cable,
  CalendarDays,
  CodeXml,
  Coins,
  Database,
  KeyRound,
  LayoutDashboard,
  Plug,
  Server,
  Settings,
  ShieldCheck,
  ShoppingBag,
  Webhook,
} from 'lucide-react';
import type { QueryClient } from '@tanstack/react-query';
import type { ComponentType, ReactNode } from 'react';
import { ModuleGate } from '../components/module-gate';
import { overviewQuery } from '../lib/queries';
import { ActivityPage } from './activity';
import { AdminPage } from './admin';
import { AlertsPage } from './alerts';
import { CalendarPage } from './calendar';
import { HostingPage } from './hosting';
import { IntegrationsPage } from './integrations';
import { KnowledgePage } from './knowledge';
import { KnowledgeSourcePage } from './knowledge/source';
import { LeetCodePage } from './leetcode';
import { McpPage } from './mcp';
import { ModulesPage } from './modules';
import { NotificationsPage } from './notifications';
import { OverviewPage } from './overview';
import { PointsPage } from './points';
import { prefetchPoints } from './points/shared';
import { SettingsPage } from './settings';
import { StorePage } from './store';
import { prefetchStore } from './store/shared';
import { TokensPage } from './tokens';
import { WebhooksPage } from './webhooks';

// The sidebar sections, in order. A section with no title has no header.
export const SECTIONS = [
  { id: 'top' },
  { id: 'members', title: 'Members' },
  { id: 'automations', title: 'Automations' },
  { id: 'knowledge', title: 'Knowledge and MCP' },
  { id: 'infrastructure', title: 'Infrastructure' },
  { id: 'bottom' },
] as const;

export type SectionId = (typeof SECTIONS)[number]['id'];

// The groups inside a section, in order, each under a small header. To add an automation, give its page one of
// these groups. Pages with no group come first in their section.
export const GROUPS = [
  { id: 'webhooks', section: 'automations', title: 'Webhooks' },
  { id: 'scheduled', section: 'automations', title: 'Scheduled jobs' },
  { id: 'bots', section: 'automations', title: 'Bots' },
] as const;

export type GroupId = (typeof GROUPS)[number]['id'];

export type PageEntry = {
  // The URL after /<org>/. An empty path is the org home page.
  path: string;
  // The sidebar label, and the page title on the module-off note.
  label: string;
  icon: ComponentType<{ className?: string }>;
  section: SectionId;
  // The group inside the section. It must be a group of the same section.
  group?: GroupId;
  // The sidebar hides the page when the API says this module is off. With a list, it hides the page when every
  // module in the list is off.
  module?: string | string[];
  // With one module set, the page shows a module-off note in place of its content when the module is off.
  gate?: boolean;
  // Only the superadmin sees the page in the sidebar.
  superadmin?: boolean;
  // The page has no sidebar item. Links on another page open it. The first part of path selects the sidebar item.
  hidden?: boolean;
  page: ComponentType;
  // Starts the main requests of the page: on a sidebar hover or focus, and when the page opens, before its module
  // check answers.
  prefetch?: (client: QueryClient, prefix: string) => void;
};

const prefetchOverview = (client: QueryClient, prefix: string) => void client.prefetchQuery(overviewQuery(prefix));

// Every org page, in sidebar order. To add a page, write the page file and add one entry here.
export const PAGES: PageEntry[] = [
  { path: '', label: 'Overview', icon: LayoutDashboard, section: 'top', page: OverviewPage, prefetch: prefetchOverview },
  { path: 'notifications', label: 'Notifications', icon: Bell, section: 'top', page: NotificationsPage },
  { path: 'points', label: 'Points', icon: Coins, section: 'members', module: 'points', gate: true, page: PointsPage, prefetch: prefetchPoints },
  { path: 'store', label: 'Store', icon: ShoppingBag, section: 'members', module: 'storefront', gate: true, page: StorePage, prefetch: prefetchStore },
  { path: 'webhooks', label: 'Webhooks', icon: Webhook, section: 'automations', group: 'webhooks', page: WebhooksPage },
  { path: 'alerts', label: 'Alerts', icon: BellRing, section: 'automations', group: 'webhooks', module: 'alerts', gate: true, page: AlertsPage },
  { path: 'calendar', label: 'Calendar sync', icon: CalendarDays, section: 'automations', group: 'scheduled', module: 'calendar', gate: true, page: CalendarPage },
  { path: 'leetcode', label: 'LeetCode', icon: CodeXml, section: 'automations', group: 'bots', module: 'leetcode', gate: true, page: LeetCodePage },
  { path: 'knowledge', label: 'Knowledge', icon: Database, section: 'knowledge', page: KnowledgePage },
  { path: 'knowledge/sources/*', label: 'Knowledge source', icon: Database, section: 'knowledge', hidden: true, page: KnowledgeSourcePage },
  { path: 'mcp', label: 'MCP', icon: Cable, section: 'knowledge', page: McpPage },
  { path: 'hosting', label: 'Hosting', icon: Server, section: 'infrastructure', module: ['runpod', 'compute'], page: HostingPage },
  { path: 'tokens', label: 'Tokens', icon: KeyRound, section: 'infrastructure', page: TokensPage },
  { path: 'activity', label: 'Activity', icon: Activity, section: 'bottom', page: ActivityPage },
  { path: 'modules', label: 'Modules', icon: Blocks, section: 'bottom', page: ModulesPage },
  { path: 'integrations', label: 'Integrations', icon: Plug, section: 'bottom', page: IntegrationsPage },
  { path: 'settings', label: 'Settings', icon: Settings, section: 'bottom', page: SettingsPage },
  { path: 'admin', label: 'Superadmin', icon: ShieldCheck, section: 'bottom', superadmin: true, page: AdminPage },
];

// Old org paths that open another page. to is relative to the old path.
export const REDIRECTS: { path: string; to: string }[] = [
  { path: 'ci', to: '../activity?tab=ci' },
  { path: 'agents', to: '../mcp' },
  { path: 'apps', to: '../hosting?tab=services' },
  { path: 'compute', to: '../hosting?tab=pods' },
];

// The element for the route of a page, inside a ModuleGate when the entry asks for one.
export function pageElement({ page: Page, module, gate, label }: PageEntry): ReactNode {
  return typeof module === 'string' && gate ? (
    <ModuleGate module={module} title={label}>
      <Page />
    </ModuleGate>
  ) : (
    <Page />
  );
}
