import { ApiError } from './api';

// Sentry in the browser. It loads only when the build has VITE_SENTRY_DSN, so other builds do not download it.
const DSN = (import.meta.env.VITE_SENTRY_DSN as string | undefined) || null;

type Sentry = typeof import('./sentry-client');
let sentry: Sentry | null = null;

export async function startMonitoring(): Promise<void> {
  if (!DSN) return;
  sentry = await import('./sentry-client');
  sentry.init({
    dsn: DSN,
    environment: (import.meta.env.VITE_SENTRY_ENVIRONMENT as string | undefined) || import.meta.env.MODE,
  });
}

// Sends an error to Sentry. API answers below 500, such as a refused form, are expected and not sent.
export function reportError(error: unknown, source: string): void {
  if (!sentry) return;
  if (error instanceof ApiError && error.status > 0 && error.status < 500) return;
  sentry.captureException(error, { tags: { source } });
}
