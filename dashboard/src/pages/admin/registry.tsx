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
  label: string;
  icon: ComponentType<{ className?: string }>;
  section: (typeof ADMIN_SECTIONS)[number]['id'];
  page: ComponentType;
};

// Every page of the superadmin space, in sidebar order. To add a page, write the page file and add one entry here.
export const ADMIN_PAGES: AdminPageEntry[] = [
  { path: '', label: 'Overview', icon: LayoutDashboard, section: 'top', page: OverviewPage },
  { path: 'orgs', label: 'Organizations', icon: Building2, section: 'orgs', page: OrganizationsPage },
  { path: 'limits', label: 'Limits', icon: Gauge, section: 'orgs', page: LimitsPage },
  { path: 'shared-apps', label: 'Shared apps', icon: Boxes, section: 'shared', page: SharedAppsPage },
  { path: 'submodules', label: 'Sub-modules', icon: Package, section: 'shared', page: SubmodulesPage },
  { path: 'publishers', label: 'Publishers', icon: BookUp, section: 'shared', page: PublishersPage },
  { path: 'server', label: 'Server', icon: Server, section: 'server', page: ServerPage },
  { path: 'services', label: 'Services', icon: Container, section: 'server', page: ServicesPage },
  { path: 'errors', label: 'Errors', icon: Bug, section: 'activity', page: ErrorsPage },
  { path: 'audit', label: 'Audit log', icon: ScrollText, section: 'activity', page: AuditPage },
];
