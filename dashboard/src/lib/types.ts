// Shapes of the Platform API responses the dashboard reads.

export type Organization = { id: number; name: string; prefix: string; guild_id: string; icon_url: string | null };

export type Branding = { logo_url: string | null; accent_color: string | null };

export type ModuleState = { name: string; description: string; enabled: boolean };

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

export type Problem = { module: string; subject: string; message: string };

export type AlertFeedSummary = {
  key: string;
  kind: string;
  enabled: boolean;
  every_hours: number;
  last_run_at: string | null;
  last_error: string | null;
  posted_7_days: number;
};

export type AppSummary = {
  name: string;
  repo: string | null;
  tag: string | null;
  status: string | null;
  deployed_at: string | null;
  error: string | null;
};

export type Overview = {
  organization: { id: number; name: string; prefix: string; branding: Branding };
  modules: ModuleState[];
  sections: {
    members: { total: number };
    points: { total: number; last_30_days: number };
    storefront: { products: number; pending_orders: number };
    compute: {
      pods: { pod_id: string; name: string; public: boolean }[];
      sessions: { pod_id: string; title: string | null; start_at: string; stop_at: string }[];
    };
    alerts: { feeds: AlertFeedSummary[] };
    apps: { apps: AppSummary[] };
    knowledge: { sources: number; crawled: number; failing: { key: string; url: string | null; error: string }[] };
    agents: {
      conversations: number;
      active_7_days: number;
      members_7_days: number;
      memories: number;
      pending_actions: number;
    };
    accounts: { linked: Record<string, number> };
    tokens: { tokens: { name: string; kind: string; scopes: string[]; last_used_at: string | null }[]; cli_tokens: number };
  };
  problems: Problem[];
  activity: AuditEntry[];
  jobs: AuditEntry[];
  generated_at: string;
};

export type CiRun = {
  workflow: string | null;
  branch: string | null;
  event: string | null;
  status: string | null;
  conclusion: string | null;
  title: string | null;
  url: string | null;
  started_at: string | null;
};

export type CiRepo = { repo: string; runs: CiRun[]; error: string | null };

export type AlertFeed = {
  key: string;
  kind: 'github_jobs' | 'hackathons';
  config: Record<string, unknown>;
  every_hours: number;
  enabled: boolean;
  webhook_set: boolean;
  seeded_at: string | null;
  last_run_at: string | null;
  last_error: string | null;
  posted: number;
};

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

export type SecretState = { name: string; description: string; set: boolean };

// Settings and superadmin

export type OrganizationDetail = Organization & {
  description: string | null;
  is_active: boolean;
  officer_role_id: string | null;
  points_per_message: number | null;
  points_cooldown: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type CalendarSettings = {
  notion_database_id: string | null;
  google_calendar_id: string | null;
  calendar_sync_enabled: boolean;
  last_sync_at: string | null;
};

export type LeetCodeSettings = { channel_id: string | null; role_ping: string | null; daily_time: string | null };

export type AvailableGuild = { id: string; name: string; icon: { url: string | null } | null; member_count?: number };

export type SuperadminDashboard = {
  available_guilds: AvailableGuild[];
  existing_orgs: OrganizationDetail[];
  officer_orgs: OrganizationDetail[];
};

export type GuildRole = { id: string; name: string; color: number; position: number; permissions: string };
