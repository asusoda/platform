// Uptime monitors and their checks.

export type UptimeCheck = {
  checked_at: string;
  up: boolean;
  status_code: number | null;
  latency_ms: number | null;
  error: string | null;
};

export type UptimeMonitor = {
  id: number;
  name: string;
  target_kind: 'url' | 'app';
  target: string;
  expected_status: string;
  timeout_seconds: number;
  interval_minutes: number;
  enabled: boolean;
  state: 'up' | 'down' | null;
  state_since: string | null;
  last_checked_at: string | null;
  last_check: UptimeCheck | null;
  uptime_24h: number | null;
  uptime_7d: number | null;
  // The last checks, oldest first
  recent: UptimeCheck[];
};

// A Hosting app that a monitor can check, and the URL that a check reads.
export type UptimeTarget = { name: string; url: string | null };
