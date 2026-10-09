// The overview response and the CI runs it lists.

import type { AuditEntry, Branding, ModuleState } from './org';

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

export type TrendDay = { date: string; value: number; failed: number };
export type TrendSeries = { key: string; title: string; unit: string; total: number; failed: number; days: TrendDay[] };
export type Trends = { days: number; series: TrendSeries[]; generated_at: string };

export type SentryIssue = {
  id: string;
  short_id: string | null;
  title: string | null;
  culprit: string | null;
  level: string | null;
  count: number;
  users: number;
  first_seen: string | null;
  last_seen: string | null;
  url: string | null;
};
export type SentryIssues = { configured: boolean; issues: SentryIssue[]; error: string | null; project_url: string | null };
