import { ApiError, send } from './api';

// Sends dashboard errors to the API error log: errors thrown in the page, and API calls that got no answer
// or a status of 500 or more. A report that cannot be sent waits and goes with the next one.

const PATHS_WITHOUT_ORG = new Set(['login', 'auth', 'store']);
const REPEAT_MS = 60_000;
const MAX_WAITING = 20;
const RETRY_MS = 30_000;

type Report = { kind: string; message: string; stack: string | null; page: string };

const lastSent = new Map<string, number>();
let waiting: { prefix: string; report: Report }[] = [];
let flushing = false;

function orgPrefix(): string | null {
  const first = location.pathname.split('/')[1] ?? '';
  return first && !PATHS_WITHOUT_ORG.has(first) ? first : null;
}

function describe(error: unknown): { kind: string; message: string; stack: string | null } {
  if (error instanceof ApiError) return { kind: 'ApiError', message: error.message, stack: error.stack ?? null };
  if (error instanceof Error) return { kind: error.name || 'Error', message: error.message, stack: error.stack ?? null };
  return { kind: 'Error', message: String(error), stack: null };
}

async function flush(): Promise<void> {
  if (flushing) return;
  flushing = true;
  try {
    while (waiting.length) {
      const next = waiting[0];
      await send(`/api/dashboard/${next.prefix}/errors/report`, 'POST', next.report);
      waiting.shift();
    }
  } catch {
    // The API is still not reachable. The reports wait for the next try.
  } finally {
    flushing = false;
  }
}

// Records an error. Expected API answers below 500, such as a refused form, are not errors.
export function reportError(error: unknown, source: string): void {
  if (error instanceof ApiError && error.status > 0 && error.status < 500) return;
  const prefix = orgPrefix();
  if (!prefix) return;
  const { kind, message, stack } = describe(error);
  const key = `${kind}:${message}`;
  const now = Date.now();
  if (now - (lastSent.get(key) ?? 0) < REPEAT_MS) return;
  lastSent.set(key, now);
  const page = `${location.pathname} (${source})`;
  waiting = [...waiting, { prefix, report: { kind, message: message.slice(0, 2000), stack: stack?.slice(0, 5000) ?? null, page } }].slice(-MAX_WAITING);
  void flush();
}

export function startErrorReports(): void {
  window.addEventListener('error', (event) => reportError(event.error ?? event.message, 'page'));
  window.addEventListener('unhandledrejection', (event) => reportError(event.reason, 'promise'));
  window.setInterval(() => {
    if (waiting.length) void flush();
  }, RETRY_MS);
}
