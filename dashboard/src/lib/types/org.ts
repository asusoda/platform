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

// A switch of GET /api/organizations/<id>/modules. A sub-module, such as points.store, names its parent module and
// is on only when the parent is on.
export type ModuleState = { name: string; description: string; enabled: boolean; parent?: string; shared?: boolean };

// An integration or a setting that a module needs. connected says whether the org or the deployment set it.
export type ModuleNeed = {
  key: string;
  label: string;
  kind: 'integration' | 'setting';
  optional: boolean;
  connected: boolean;
};

// A shared sub-module of a module, such as knowledge.asu: content made once for every org.
export type ModuleSubmodule = { name: string; key: string; title: string; description: string };

// A sub-module of a module card, with its own switch key such as points.store.
export type SubmoduleSwitch = { key: string; title: string; description: string; shared: boolean; enabled: boolean };

// A module, a sub-module card (Discord) or a layer (Hosting) on Explore. ready is false while a need that is not
// optional is not connected.
export type CatalogModule = {
  name: string;
  title: string;
  description: string;
  // null for a layer
  category: string | null;
  // The parent module of a sub-module card, such as bot for bot.leetcode
  parent: string | null;
  switchable: boolean;
  enabled: boolean;
  ready: boolean;
  needs: ModuleNeed[];
  submodules: SubmoduleSwitch[];
  shared_content: ModuleSubmodule[];
  // The limits this module's use counts against
  limits: { key: string; label: string; window: string | null; paid_by: 'org' | 'metered' }[];
};

export type ModuleCatalog = { categories: string[]; modules: CatalogModule[]; layers: CatalogModule[] };

export type SecretState = { name: string; description: string; set: boolean };

// A connected service whose tools a token can get, with its scopes and the limits it takes.
export type TokenIntegration = {
  key: string;
  title: string;
  connected: boolean;
  // Scopes that give the integration's own tools
  scopes: string[];
  // Platform scopes that call the integration for the agent
  through?: string[];
  limits: string[];
  // The Platform tools each of its scopes gives, by scope
  tools?: Record<string, string[]>;
  // The tools come from the service's own MCP server
  remote?: boolean;
  // The modules that use the integration
  used_by?: string[];
};

export type MachineToken = {
  id: number;
  name: string;
  kind: string;
  scopes: string[];
  // Per-integration limits, such as { github: { repos: ['my-org/*'] } }
  limits: Record<string, Record<string, string[]>>;
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

// A shared sub-module that an org subscribes to with its switch (GET /api/dashboard/<org>/submodules). name is the
// short name, such as asu; key is the switch key, such as knowledge.asu.
export type Submodule = {
  name: string;
  key: string;
  title: string;
  description: string;
  // null for a sub-module with no pages, such as feeds.jobs
  key_prefix: string | null;
  pages: number;
  queries: string[];
  feeds: string[];
  // Shared pages and their last crawl, for every subscriber
  sources: number;
  last_crawl: string | null;
  subscribed: boolean;
  subscribers: number;
  // The module the sub-module belongs to
  modules: string[];
  // What the sub-module brings and who pays for each part
  parts: { kind: 'pages' | 'queries' | 'feeds'; count: number; paid_by: 'org' | 'shared'; module: string }[];
};

// GET /api/dashboard/<org>/tool-groups. allowed is null when every group is allowed.
export type ToolGroupLayer = 'base' | 'service' | 'module';
export type ToolGroup = { key: string; layer: ToolGroupLayer; tools: number | null };
export type ToolGroups = { allowed: string[] | null; groups: ToolGroup[] };
