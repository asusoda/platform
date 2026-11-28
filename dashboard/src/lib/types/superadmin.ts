// The superadmin space: the org list, Discord servers and roles, and shared submodules.

import type { OrganizationDetail } from './org';

export type AvailableGuild = { id: string; name: string; icon: { url: string | null } | null; member_count?: number };

export type SuperadminDashboard = {
  available_guilds: AvailableGuild[];
  existing_orgs: OrganizationDetail[];
  officer_orgs: OrganizationDetail[];
};

// One org of GET /api/superadmin/orgs, which needs no bot.
export type SuperadminOrg = {
  id: number;
  name: string;
  prefix: string;
  guild_id: string;
  icon_url: string | null;
  is_active: boolean;
  officer_role_id: string | null;
  created_at: string | null;
  members: number;
  modules_on: string[];
  near: string[];
  open_errors: number;
  last_activity: string | null;
};

export type GuildRole = { id: string; name: string; color: number; position: number; permissions: string };

// One submodule of GET /api/superadmin/submodules.
export type SubmoduleOverview = {
  key: string;
  title: string;
  origin: string;
  status: string;
  subscribers: number;
  sources: number;
  passages: number;
  failing: { key: string; error: string }[];
};
