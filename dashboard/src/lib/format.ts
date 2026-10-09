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
  return elapsed((parse(stop).getTime() - parse(start).getTime()) / 1000);
}

// A length of time in seconds, as 45m, 2h or 1h 30m.
export function elapsed(seconds: number): string {
  const minutes = Math.max(0, Math.round(seconds / 60));
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest}m`;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

// One formatter for all calls: a new Intl.NumberFormat for each row of a long table is slow.
const compactFormat = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 });
const fullFormat = new Intl.NumberFormat('en');

export function compact(n: number): string {
  return compactFormat.format(n);
}

// A count with thousands separators, such as 2,000.
export function count(n: number): string {
  return fullFormat.format(n);
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

// A byte count as 512 B, 1.2 KB or 3.4 GB.
export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = n / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
}

const pad = (n: number) => String(n).padStart(2, '0');

// A datetime-local value (2026-10-08T18:30) as ISO 8601 with the browser's offset for that date.
export function localToIso(value: string): string {
  const date = new Date(value);
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? '+' : '-';
  const abs = Math.abs(offset);
  return `${value.slice(0, 16)}:00${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}

// A Date as a datetime-local value in the browser's time zone.
export function toLocalInput(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// An API timestamp as a short local date and time, such as Thu, Oct 8, 6:30 PM.
export function when(iso: string): string {
  return parse(iso).toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}
