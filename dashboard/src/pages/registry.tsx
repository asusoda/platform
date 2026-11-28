import {
  Activity,
  BriefcaseBusiness,
  CalendarDays,
  CodeXml,
  Coins,
  Compass,
  Database,
  HeartPulse,
  Plug,
  LayoutDashboard,
  Cpu,
  Server,
  Settings,
  ShoppingBag,
  Trophy,
  Megaphone,
} from 'lucide-react';
import type { QueryClient } from '@tanstack/react-query';
import type { ComponentType, ReactNode } from 'react';
import { ModuleGate } from '../components/module-gate';
import { overviewQuery } from '../lib/queries';
import { ActivityPage } from './activity';
import { HackathonWebhookPage, JobWebhookPage } from './feeds';
import { CalendarPage } from './calendar';
import { ExplorePage } from './explore';
import { ModulePage } from './explore/module';
import { GodfatherPage } from './godfather';
import { HostingPage } from './hosting';
import { KnowledgePage } from './knowledge';
import { KnowledgeSourcePage } from './knowledge/source';
import { LeetCodePage } from './leetcode';
import { OverviewPage } from './overview';
import { PointsPage } from './points';
import { prefetchPoints } from './points/shared';
import { SettingsPage } from './settings';
import { StorePage } from './store';
import { prefetchStore } from './store/shared';
import { ConnectionsPage } from './connections';
import { UptimePage } from './uptime';
import { AlertsPage } from './alerts';

// The sidebar sections, in order. A section with no title has no header. They follow the categories on Explore.
export const SECTIONS = [
  { id: 'top' },
  { id: 'members', title: 'Members' },
  { id: 'ai', title: 'AI' },
  { id: 'automations', title: 'Automations' },
  { id: 'discord', title: 'Discord' },
  { id: 'compute', title: 'Compute' },
  { id: 'apps', title: 'Apps' },
  { id: 'bottom' },
] as const;

export type SectionId = (typeof SECTIONS)[number]['id'];

export type PageEntry = {
  // The URL after /<org>/. An empty path is the org home page.
  path: string;
  // The sidebar label and the page title.
  label: string;
  // One short line under the page title.
  description?: string;
  // The docs page for the Docs link of the header, such as modules/points. See docsPage in lib/links.ts.
  docs: string;
  icon: ComponentType<{ className?: string }>;
  section: SectionId;
  // The sidebar hides the page when the API says this module is off. With a list, it hides the page when every
  // module in the list is off.
  module?: string | string[];
  // With one module set, the page shows a module-off note in place of its content when the module is off.
  gate?: boolean;
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
  { path: '', label: 'Overview', docs: 'concepts', icon: LayoutDashboard, section: 'top', page: OverviewPage, prefetch: prefetchOverview },
  { path: 'explore', label: 'Explore', description: 'Features, shared content and integrations.', docs: 'concepts', icon: Compass, section: 'top', page: ExplorePage },
  { path: 'explore/:module', label: 'Explore', docs: 'concepts', icon: Compass, section: 'top', hidden: true, page: ModulePage },
  { path: 'points', label: 'Points', description: 'Members, their points and the events that gave them.', docs: 'modules/points', icon: Coins, section: 'members', module: 'points', gate: true, page: PointsPage, prefetch: prefetchPoints },
  { path: 'store', label: 'Store', description: 'Merch that members buy with points.', docs: 'modules/store', icon: ShoppingBag, section: 'members', module: 'points.store', gate: true, page: StorePage, prefetch: prefetchStore },
  { path: 'knowledge', label: 'Knowledge', description: 'Pages and documents that agents search.', docs: 'modules/knowledge', icon: Database, section: 'ai', module: 'knowledge', gate: true, page: KnowledgePage },
  { path: 'knowledge/sources/*', label: 'Knowledge', docs: 'modules/knowledge', icon: Database, section: 'ai', module: 'knowledge', gate: true, hidden: true, page: KnowledgeSourcePage },
  { path: 'job-alerts', label: 'Job alerts', description: 'New internship and new grad roles, posted to Discord.', docs: 'modules/feeds', icon: BriefcaseBusiness, section: 'automations', module: 'feeds', gate: true, page: JobWebhookPage },
  { path: 'hackathons', label: 'Hackathons', description: 'Upcoming hackathons, posted to Discord.', docs: 'modules/feeds', icon: Trophy, section: 'automations', module: 'feeds', gate: true, page: HackathonWebhookPage },
  { path: 'calendar', label: 'Calendar', description: 'Notion events copied to Google Calendar.', docs: 'modules/calendar', icon: CalendarDays, section: 'automations', module: 'calendar', gate: true, page: CalendarPage },
  { path: 'uptime', label: 'Uptime', description: 'Checks of your sites and Hosting apps.', docs: 'modules/uptime', icon: HeartPulse, section: 'automations', module: 'uptime', gate: true, page: UptimePage },
  { path: 'leetcode', label: 'LeetCode', description: 'The daily problem post in your Discord server.', docs: 'modules/leetcode', icon: CodeXml, section: 'discord', module: 'bot.leetcode', gate: true, page: LeetCodePage },
  { path: 'godfather', label: 'Godfather', description: 'Pods that members connect to with the Godfather CLI.', docs: 'modules/godfather', icon: Cpu, section: 'compute', module: 'godfather', gate: true, page: GodfatherPage },
  { path: 'hosting', label: 'Hosting', description: 'Bots, sites and services the org deploys.', docs: 'modules/hosting', icon: Server, section: 'apps', module: 'hosting', gate: true, page: HostingPage },
  { path: 'alerts', label: 'Alerts', description: "Where the org's events and feeds go.", docs: 'codebase/webhooks', icon: Megaphone, section: 'bottom', page: AlertsPage },
  { path: 'connections', label: 'Connections', description: 'Agents and services that call Platform.', docs: 'codebase/authentication', icon: Plug, section: 'bottom', page: ConnectionsPage },
  { path: 'activity', label: 'Activity', description: 'What happened in your org.', docs: 'codebase/frontends#officer-dashboard', icon: Activity, section: 'bottom', page: ActivityPage },
  { path: 'settings', label: 'Settings', description: "The org's profile, branding, secrets and limits.", docs: 'codebase/frontends#officer-dashboard', icon: Settings, section: 'bottom', page: SettingsPage },
];

// Old org paths that open another page. to is relative to the old path, or absolute when it starts with /.
export const REDIRECTS: { path: string; to: string }[] = [
  { path: 'admin', to: '/admin' },
  { path: 'ci', to: '../activity?tab=ci' },
  { path: 'notifications', to: '../activity?tab=notifications' },
  { path: 'modules', to: '../explore' },
  { path: 'integrations', to: '../explore?tab=integrations' },
  { path: 'apps', to: '../hosting' },
  { path: 'compute', to: '../godfather' },
  { path: 'mcp', to: '../connections' },
  { path: 'tokens', to: '../connections' },
  { path: 'webhooks', to: '../alerts' },
  { path: 'agents', to: '../explore' },
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
