// Display helpers for times, numbers and run states.

export function timeAgo(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return 'never';
  const then = new Date(iso.endsWith('Z') || /[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
  const seconds = Math.round((now.getTime() - then.getTime()) / 1000);
  const future = seconds < 0;
  const s = Math.abs(seconds);
  const [value, unit] =
    s < 60 ? [s, 's'] : s < 3600 ? [Math.floor(s / 60), 'm'] : s < 86400 ? [Math.floor(s / 3600), 'h'] : [Math.floor(s / 86400), 'd'];
  if (s < 10) return 'just now';
  return future ? `in ${value}${unit}` : `${value}${unit} ago`;
}

export function compact(n: number): string {
  return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(n);
}

export type Tone = 'ok' | 'warn' | 'bad' | 'muted' | 'accent';

export function runTone(status: string | null, conclusion: string | null): Tone {
  if (status && status !== 'completed') return 'accent';
  if (conclusion === 'success') return 'ok';
  if (conclusion === 'failure' || conclusion === 'timed_out' || conclusion === 'startup_failure') return 'bad';
  if (conclusion === 'cancelled' || conclusion === 'action_required') return 'warn';
  return 'muted';
}

export function deployTone(status: string | null): Tone {
  if (status === 'healthy') return 'ok';
  if (status === 'failed') return 'bad';
  if (status === 'deploying') return 'accent';
  return 'muted';
}
