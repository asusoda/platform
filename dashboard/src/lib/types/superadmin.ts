// The superadmin page: Discord servers and roles.

import type { OrganizationDetail } from './org';

export type AvailableGuild = { id: string; name: string; icon: { url: string | null } | null; member_count?: number };

export type SuperadminDashboard = {
  available_guilds: AvailableGuild[];
  existing_orgs: OrganizationDetail[];
  officer_orgs: OrganizationDetail[];
};

export type GuildRole = { id: string; name: string; color: number; position: number; permissions: string };
