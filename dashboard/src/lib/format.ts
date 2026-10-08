// Display helpers for times, numbers and run states.

// Reads an API timestamp; one with no offset is UTC.
function parse(iso: string): Date {
  return new Date(iso.endsWith('Z') || /[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
}

export function timeAgo(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return 'never';
  const then = parse(iso);
  const seconds = Math.round((now.getTime() - then.getTime()) / 1000);
  const future = seconds < 0;
  const s = Math.abs(seconds);
  const [value, unit] =
    s < 60 ? [s, 's'] : s < 3600 ? [Math.floor(s / 60), 'm'] : s < 86400 ? [Math.floor(s / 3600), 'h'] : [Math.floor(s / 86400), 'd'];
  if (s < 10) return 'just now';
  return future ? `in ${value}${unit}` : `${value}${unit} ago`;
}

// The time between two timestamps, as 45m, 2h or 1h 30m.
export function duration(start: string, stop: string): string {
  const minutes = Math.max(0, Math.round((parse(stop).getTime() - parse(start).getTime()) / 60_000));
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest}m`;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

export function compact(n: number): string {
  return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(n);
}

export type Tone = 'ok' | 'warn' | 'bad' | 'muted' | 'active';

export function runTone(status: string | null, conclusion: string | null): Tone {
  if (status && status !== 'completed') return 'active';
  if (conclusion === 'success') return 'ok';
  if (conclusion === 'failure' || conclusion === 'timed_out' || conclusion === 'startup_failure') return 'bad';
  if (conclusion === 'cancelled' || conclusion === 'action_required') return 'warn';
  return 'muted';
}

export function deployTone(status: string | null): Tone {
  if (status === 'healthy') return 'ok';
  if (status === 'failed') return 'bad';
  if (status === 'deploying') return 'active';
  return 'muted';
}

export function podTone(status: string | null | undefined): Tone {
  if (status === 'RUNNING') return 'ok';
  if (status === 'EXITED' || status === 'TERMINATED') return 'muted';
  if (status === 'CREATED' || status === 'RESTARTING') return 'active';
  return 'warn';
}

// A key with slashes as a URL path: each segment is encoded, the slashes stay.
export function keyPath(key: string): string {
  return key.split('/').map(encodeURIComponent).join('/');
}
