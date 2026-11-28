import {
  Blocks,
  CalendarDays,
  CodeXml,
  Coins,
  Cpu,
  Database,
  Gamepad2,
  HeartPulse,
  Plug,
  Rss,
  Server,
  ShoppingBag,
  type LucideIcon,
} from 'lucide-react';
import type { CatalogModule } from './types';

// Whether a module matches the search text, by its name, title, description, category, needs and submodules.
export function matches(m: CatalogModule, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const text = [m.name, m.title, m.description, m.category, ...m.needs.map((n) => n.label), ...m.submodules.map((p) => p.title)];
  return text.join(' ').toLowerCase().includes(q);
}

// The dashboard page of each module that has one, relative to /<org>/.
export const MODULE_PAGES: Record<string, string> = {
  points: 'points',
  storefront: 'store',
  calendar: 'calendar',
  leetcode: 'leetcode',
  godfather: 'godfather',
  runpod: 'hosting',
  feeds: 'job-alerts',
  knowledge: 'knowledge',
  uptime: 'uptime',
};

// The docs page of each module. A module with no page of its own links to the concepts page.
const MODULE_DOCS: Record<string, string> = {
  knowledge: 'modules/knowledge',
  points: 'modules/points',
  storefront: 'modules/storefront',
  feeds: 'modules/feeds',
  calendar: 'modules/calendar',
  uptime: 'modules/uptime',
  leetcode: 'modules/leetcode',
  games: 'modules/discord-bot',
  godfather: 'modules/godfather',
  runpod: 'modules/runpod-apps',
  integrations: 'codebase/integrations',
};

export const moduleDocs = (name: string) => MODULE_DOCS[name] ?? 'concepts';

// One icon for each module, for the sidebar, Explore and the module page.
const MODULE_ICONS: Record<string, LucideIcon> = {
  knowledge: Database,
  points: Coins,
  storefront: ShoppingBag,
  feeds: Rss,
  calendar: CalendarDays,
  uptime: HeartPulse,
  leetcode: CodeXml,
  games: Gamepad2,
  godfather: Cpu,
  runpod: Server,
  integrations: Plug,
};

export const moduleIcon = (name: string): LucideIcon => MODULE_ICONS[name] ?? Blocks;

// The name the dashboard shows for a module, or for the part of a module that a notification or row names.
const MODULE_LABELS: Record<string, string> = {
  knowledge: 'Knowledge',
  points: 'Points',
  storefront: 'Store',
  feeds: 'Feeds',
  calendar: 'Calendar',
  uptime: 'Uptime',
  leetcode: 'LeetCode',
  games: 'Games',
  godfather: 'Godfather',
  runpod: 'Hosting',
  integrations: 'Integrations',
  alerts: 'Alerts',
  organizations: 'Settings',
  users: 'Members',
  ci: 'CI',
  auth: 'Sign-in',
  dashboard: 'Dashboard',
  mcp: 'MCP',
  // Older notifications, from before the two feed modules became feeds
  job_webhook: 'Job alerts',
  hackathon_webhook: 'Hackathons',
  apps: 'Hosting',
  app: 'Hosting',
  errors: 'Errors',
  jobs: 'Jobs',
  order: 'Store',
  member: 'Members',
};

export const moduleLabel = (module: string) => MODULE_LABELS[module] ?? module;

// The module of a notification. Some notifications name a part of a module, such as order for the store.
const NOTIFICATION_MODULES: Record<string, string> = {
  apps: 'runpod',
  app: 'runpod',
  order: 'storefront',
  job_webhook: 'feeds',
  hackathon_webhook: 'feeds',
};

export const notificationModule = (module: string) => NOTIFICATION_MODULES[module] ?? module;
