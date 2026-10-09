// The parts of the Sentry SDK the dashboard uses. monitoring.ts loads this file only when VITE_SENTRY_DSN is set.
export { captureException, init } from '@sentry/react';
