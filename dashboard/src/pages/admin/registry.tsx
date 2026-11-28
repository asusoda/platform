import { Boxes, BookUp, Building2, Bug, Container, Gauge, LayoutDashboard, Package, ScrollText, Server } from 'lucide-react';
import type { ComponentType } from 'react';
import { AuditPage } from './audit';
import { ErrorsPage } from './errors';
import { LimitsPage } from './limits';
import { OrganizationsPage } from './organizations';
import { OverviewPage } from './overview';
import { PublishersPage } from './publishers';
import { ServerPage } from './server';
import { ServicesPage } from './services';
import { SharedAppsPage } from './shared-apps';
import { SubmodulesPage } from './submodules';

// The sidebar sections of the superadmin space, in order. The first has no header.
export const ADMIN_SECTIONS = [
  { id: 'top' },
  { id: 'orgs', title: 'Organizations' },
  { id: 'shared', title: 'Shared' },
  { id: 'server', title: 'Server' },
  { id: 'activity', title: 'Activity' },
] as const;

export type AdminPageEntry = {
  // The URL after /admin/. An empty path is the Overview.
  path: string;
  // The sidebar label and the page title.
  label: string;
  // One short line under the page title.
  description?: string;
  // The docs page for the Docs link of the header. See docsPage in lib/links.ts.
  docs: string;
  icon: ComponentType<{ className?: string }>;
  section: (typeof ADMIN_SECTIONS)[number]['id'];
  page: ComponentType;
};

// Every page of the superadmin space, in sidebar order. To add a page, write the page file and add one entry here.
export const ADMIN_PAGES: AdminPageEntry[] = [
  { path: '', label: 'Overview', description: 'Every org and the server at a glance.', docs: 'codebase/frontends#superadmin-space', icon: LayoutDashboard, section: 'top', page: OverviewPage },
  { path: 'orgs', label: 'Organizations', description: 'Orgs, their officer roles and Discord servers.', docs: 'codebase/authentication#officer-sign-in', icon: Building2, section: 'orgs', page: OrganizationsPage },
  { path: 'limits', label: 'Limits', description: 'Marked at 80% of a limit.', docs: 'codebase/limits', icon: Gauge, section: 'orgs', page: LimitsPage },
  { path: 'shared-apps', label: 'Shared apps', description: 'Owned by the deployment, used by orgs.', docs: 'modules/hosting#shared-apps', icon: Boxes, section: 'shared', page: SharedAppsPage },
  { path: 'submodules', label: 'Sub-modules', description: 'Shared content that orgs subscribe to.', docs: 'modules/submodules', icon: Package, section: 'shared', page: SubmodulesPage },
  { path: 'publishers', label: 'Publishers', description: 'Orgs that can publish knowledge to other orgs.', docs: 'modules/knowledge', icon: BookUp, section: 'shared', page: PublishersPage },
  { path: 'server', label: 'Server', description: 'Load, memory, disk and processes.', docs: 'codebase/operations', icon: Server, section: 'server', page: ServerPage },
  { path: 'services', label: 'Services', description: 'Containers on the server and who owns them.', docs: 'codebase/operations#host-agent', icon: Container, section: 'server', page: ServicesPage },
  { path: 'errors', label: 'Errors', description: 'Errors of every org and the server.', docs: 'codebase/operations#health-logs-and-errors', icon: Bug, section: 'activity', page: ErrorsPage },
  { path: 'audit', label: 'Audit log', description: 'Changes by officers, tokens and jobs.', docs: 'codebase/authentication#access-checks', icon: ScrollText, section: 'activity', page: AuditPage },
];
