// Alerts: the org's destinations (outbound webhooks), the events each one gets, and the feeds that post to them.

import type { Feed } from './feeds';

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

export type WebhookFeed = Pick<Feed, 'key' | 'kind' | 'enabled' | 'destination_id' | 'webhook_set' | 'last_run_at' | 'last_error'>;

export type WebhookList = {
  webhooks: Webhook[];
  events: WebhookEvent[];
  kinds: WebhookKind[];
  // The feeds of the org, when the feeds module is on
  feeds: WebhookFeed[];
  secrets_key: boolean;
};

export type WebhookTest = { ok: boolean; message: string };

// One message that Platform sent or tried to send: an event, a feed item, a test or a LeetCode post.
export type Delivery = {
  id: number;
  destination_id: number | null;
  source: 'event' | 'feed' | 'leetcode' | 'test';
  // The event key, the feed key or the LeetCode scope
  ref: string;
  title: string;
  status: 'sent' | 'failed';
  error: string | null;
  // A link to the Discord message, for a bot post
  message_url: string | null;
  created_at: string | null;
};

export type DeliveryList = { deliveries: Delivery[]; next: number | null };
