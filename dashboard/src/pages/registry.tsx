import {
  Activity,
  Bell,
  BellRing,
  Bot,
  Boxes,
  CalendarDays,
  CodeXml,
  Coins,
  Cpu,
  Database,
  KeyRound,
  LayoutDashboard,
  Plug,
  Settings,
  ShieldCheck,
  ShoppingBag,
} from 'lucide-react';
import type { ComponentType, ReactNode } from 'react';
import { ModuleGate } from '../components/module-gate';
import { ActivityPage } from './activity';
import { AdminPage } from './admin';
import { AgentsPage } from './agents';
import { AlertsPage } from './alerts';
import { AppsPage } from './apps';
import { CalendarPage } from './calendar';
import { ComputePage } from './compute';
import { IntegrationsPage } from './integrations';
import { KnowledgePage } from './knowledge';
import { LeetCodePage } from './leetcode';
import { NotificationsPage } from './notifications';
import { OverviewPage } from './overview';
import { PointsPage } from './points';
import { SettingsPage } from './settings';
import { StorePage } from './store';
import { TokensPage } from './tokens';

// The sidebar sections, in order. A section with no title has no header.
export const SECTIONS = [
  { id: 'top' },
  { id: 'members', title: 'Members' },
  { id: 'automations', title: 'Automations' },
  { id: 'knowledge', title: 'Knowledge and agents' },
  { id: 'infrastructure', title: 'Infrastructure' },
  { id: 'bottom' },
] as const;

export type SectionId = (typeof SECTIONS)[number]['id'];

export type PageEntry = {
  // The URL after /<org>/. An empty path is the org home page.
  path: string;
  // The sidebar label, and the page title on the module-off note.
  label: string;
  icon: ComponentType<{ className?: string }>;
  section: SectionId;
  // The sidebar hides the page when the API says this module is off.
  module?: string;
  // With module set, the page shows a module-off note in place of its content when the module is off.
  gate?: boolean;
  // Only the superadmin sees the page in the sidebar.
  superadmin?: boolean;
  page: ComponentType;
};

// Every org page, in sidebar order. To add a page, write the page file and add one entry here.
export const PAGES: PageEntry[] = [
  { path: '', label: 'Overview', icon: LayoutDashboard, section: 'top', page: OverviewPage },
  { path: 'notifications', label: 'Notifications', icon: Bell, section: 'top', page: NotificationsPage },
  { path: 'points', label: 'Points', icon: Coins, section: 'members', module: 'points', gate: true, page: PointsPage },
  { path: 'store', label: 'Store', icon: ShoppingBag, section: 'members', module: 'storefront', gate: true, page: StorePage },
  { path: 'alerts', label: 'Alerts', icon: BellRing, section: 'automations', module: 'alerts', gate: true, page: AlertsPage },
  { path: 'calendar', label: 'Calendar', icon: CalendarDays, section: 'automations', module: 'calendar', gate: true, page: CalendarPage },
  { path: 'leetcode', label: 'LeetCode', icon: CodeXml, section: 'automations', module: 'leetcode', gate: true, page: LeetCodePage },
  { path: 'knowledge', label: 'Knowledge', icon: Database, section: 'knowledge', page: KnowledgePage },
  { path: 'agents', label: 'Agents', icon: Bot, section: 'knowledge', page: AgentsPage },
  { path: 'compute', label: 'Compute', icon: Cpu, section: 'infrastructure', module: 'compute', gate: true, page: ComputePage },
  { path: 'apps', label: 'Apps', icon: Boxes, section: 'infrastructure', page: AppsPage },
  { path: 'tokens', label: 'Tokens', icon: KeyRound, section: 'infrastructure', page: TokensPage },
  { path: 'activity', label: 'Activity', icon: Activity, section: 'bottom', page: ActivityPage },
  { path: 'integrations', label: 'Integrations', icon: Plug, section: 'bottom', page: IntegrationsPage },
  { path: 'settings', label: 'Settings', icon: Settings, section: 'bottom', page: SettingsPage },
  { path: 'admin', label: 'Superadmin', icon: ShieldCheck, section: 'bottom', superadmin: true, page: AdminPage },
];

// Old org paths that open another page. to is relative to the old path.
export const REDIRECTS: { path: string; to: string }[] = [{ path: 'ci', to: '../activity?tab=ci' }];

// The element for the route of a page, inside a ModuleGate when the entry asks for one.
export function pageElement({ page: Page, module, gate, label }: PageEntry): ReactNode {
  return module && gate ? (
    <ModuleGate module={module} title={label}>
      <Page />
    </ModuleGate>
  ) : (
    <Page />
  );
}
