// Alert feeds and their history.

// A feed that a pack offers, with the kind and config to create it.
export type AlertPreset = {
  pack: string;
  pack_title: string;
  key: string;
  title: string;
  description: string;
  kind: 'github_jobs' | 'hackathons';
  config: Record<string, unknown>;
  every_hours: number;
  added: boolean;
};

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

export type AlertRun = {
  started_at: string;
  duration_ms: number;
  found: number | null;
  new: number | null;
  posted: number;
  recorded: boolean;
  error: string | null;
};

export type AlertHistory = {
  runs: AlertRun[];
  items: { title: string; posted: boolean; created_at: string }[];
};
