// Outbound webhooks, the events they send, and the alert feeds that post to their own webhooks.

import type { AlertFeed } from './alerts';

export type WebhookEvent = {
  key: string;
  label: string;
  description: string;
  module: string | null;
};

export type WebhookKind = { key: string; label: string; example: string };

export type Webhook = {
  id: number;
  name: string;
  kind: string;
  // The host and the end of the webhook id. The URL itself is never returned.
  url_hint: string;
  events: string[];
  enabled: boolean;
  last_sent_at: string | null;
  last_error: string | null;
  created_at: string | null;
  created_by: string | null;
};

export type WebhookFeed = Pick<AlertFeed, 'key' | 'kind' | 'enabled' | 'webhook_set' | 'last_run_at' | 'last_error'>;

export type WebhookList = {
  webhooks: Webhook[];
  events: WebhookEvent[];
  kinds: WebhookKind[];
  // The alerts module is on, and feeds lists its feeds.
  alerts: boolean;
  feeds: WebhookFeed[];
  secrets_key: boolean;
};

export type WebhookTest = { ok: boolean; message: string };
