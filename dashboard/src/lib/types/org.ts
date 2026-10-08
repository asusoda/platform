// Orgs, their settings, secrets, tokens and the audit log.

export type Organization = { id: number; name: string; prefix: string; guild_id: string; icon_url: string | null };

export type OrganizationDetail = Organization & {
  description: string | null;
  is_active: boolean;
  officer_role_id: string | null;
  points_per_message: number | null;
  points_cooldown: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type Branding = { logo_url: string | null; accent_color: string | null; website_url: string | null };

export type ModuleState = { name: string; description: string; enabled: boolean };

export type SecretState = { name: string; description: string; set: boolean };

export type MachineToken = {
  id: number;
  name: string;
  kind: string;
  scopes: string[];
  display: string;
  created_by: string | null;
  created_at: string | null;
  expires_at: string | null;
  last_used_at: string | null;
};

export type AuditEntry = {
  id: number;
  created_at: string | null;
  source: string;
  action: string;
  org: string | null;
  actor_kind: string | null;
  actor_id: string | null;
  status: number | null;
  details: Record<string, unknown> | null;
};
