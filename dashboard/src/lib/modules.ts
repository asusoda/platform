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

// Whether a module matches the search text, by its name, title, description, category, needs, sub-modules and
// shared content.
export function matches(m: CatalogModule, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const text = [
    m.name,
    m.title,
    m.description,
    m.category ?? '',
    ...m.needs.map((n) => n.label),
    ...m.submodules.map((s) => s.title),
    ...m.shared_content.map((p) => p.title),
  ];
  return text.join(' ').toLowerCase().includes(q);
}

// The dashboard page of each module that has one, relative to /<org>/.
export const MODULE_PAGES: Record<string, string> = {
  points: 'points',
  'points.store': 'store',
  calendar: 'calendar',
  'bot.leetcode': 'leetcode',
  godfather: 'godfather',
  hosting: 'hosting',
  feeds: 'job-alerts',
  knowledge: 'knowledge',
  uptime: 'uptime',
};

// The docs page of each module. A module with no page of its own links to the concepts page.
const MODULE_DOCS: Record<string, string> = {
  knowledge: 'modules/knowledge',
  points: 'modules/points',
  'points.store': 'modules/store',
  'points.leaderboard': 'modules/points',
  'points.checkins': 'modules/points',
  feeds: 'modules/feeds',
  calendar: 'modules/calendar',
  uptime: 'modules/uptime',
  'bot.leetcode': 'modules/leetcode',
  'bot.games': 'modules/discord-bot',
  godfather: 'modules/godfather',
  hosting: 'modules/hosting',
  integrations: 'codebase/integrations',
};

export const moduleDocs = (name: string) => MODULE_DOCS[name] ?? 'concepts';

// One icon for each module, for the sidebar, Explore and the module page.
const MODULE_ICONS: Record<string, LucideIcon> = {
  knowledge: Database,
  points: Coins,
  'points.store': ShoppingBag,
  feeds: Rss,
  calendar: CalendarDays,
  uptime: HeartPulse,
  'bot.leetcode': CodeXml,
  'bot.games': Gamepad2,
  godfather: Cpu,
  hosting: Server,
  integrations: Plug,
};

export const moduleIcon = (name: string): LucideIcon => MODULE_ICONS[name] ?? Blocks;

// The name the dashboard shows for a module, or for the part of a module that a notification or row names.
const MODULE_LABELS: Record<string, string> = {
  knowledge: 'Knowledge',
  points: 'Points',
  'points.store': 'Store',
  'points.leaderboard': 'Leaderboard',
  'points.checkins': 'Check-ins',
  feeds: 'Feeds',
  calendar: 'Calendar',
  uptime: 'Uptime',
  'bot.leetcode': 'LeetCode',
  'bot.games': 'Games',
  godfather: 'Godfather',
  hosting: 'Hosting',
  integrations: 'Integrations',
  alerts: 'Alerts',
  organizations: 'Settings',
  members: 'Members',
  users: 'Members',
  ci: 'CI',
  auth: 'Sign-in',
  dashboard: 'Dashboard',
  mcp: 'MCP',
  // Older names, from before the renames
  storefront: 'Store',
  leetcode: 'LeetCode',
  games: 'Games',
  runpod: 'Hosting',
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
  apps: 'hosting',
  app: 'hosting',
  runpod: 'hosting',
  order: 'points.store',
  storefront: 'points.store',
  leetcode: 'bot.leetcode',
  games: 'bot.games',
  job_webhook: 'feeds',
  hackathon_webhook: 'feeds',
};

export const notificationModule = (module: string) => NOTIFICATION_MODULES[module] ?? module;
