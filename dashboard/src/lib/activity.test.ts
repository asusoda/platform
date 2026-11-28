import { describe, expect, it } from 'vitest';
import { auditModule, fromAudit, fromDeliveries, fromNotifications, mergeTimeline } from './activity';
import type { AuditEntry, Delivery, Notification } from './types';

const note = (over: Partial<Notification>): Notification => ({
  id: 'event-1',
  module: 'knowledge',
  subject: 'club/faq',
  message: 'The page answered 503',
  link: 'knowledge',
  kind: 'event',
  level: 'error',
  at: '2026-11-28T10:00:00Z',
  resolved_at: null,
  resolved_by: null,
  ...over,
});

const entry = (over: Partial<AuditEntry>): AuditEntry => ({
  id: 1,
  created_at: '2026-11-28T09:00:00+00:00',
  source: 'api',
  action: 'PUT /api/points/<prefix>/users/<id>',
  org: 'soda',
  actor_kind: 'officer',
  actor_id: '42',
  status: 200,
  details: null,
  ...over,
});

describe('timeline rows', () => {
  it('leaves problems out and marks error events', () => {
    const rows = fromNotifications([
      note({ id: 'problem-1', kind: 'problem', at: null }),
      note({ id: 'event-2', module: 'errors' }),
      note({ id: 'event-3', module: 'apps', level: 'info' }),
    ]);
    expect(rows.map((r) => [r.kind, r.module, r.tone])).toEqual([
      ['error', 'errors', 'bad'],
      ['event', 'runpod', 'ok'],
    ]);
  });

  it('splits audit rows into changes and job runs, with their module', () => {
    const rows = fromAudit([
      entry({}),
      entry({ id: 2, action: 'job feeds.run_feeds', actor_kind: 'job', details: { result: 'failed' } }),
      entry({ id: 3, action: 'POST /api/compute/<prefix>/pods', status: 500 }),
    ]);
    expect(rows.map((r) => [r.kind, r.module, r.tone])).toEqual([
      ['change', 'points', 'ok'],
      ['run', 'feeds', 'bad'],
      ['change', 'godfather', 'bad'],
    ]);
    expect(auditModule('PUT /api/organizations/<int:org_id>/settings')).toBe('organizations');
  });

  it('shows a LeetCode post under LeetCode with a link to the message', () => {
    const post: Delivery = {
      id: 5,
      destination_id: null,
      source: 'leetcode',
      ref: 'daily',
      title: 'Daily LeetCode: Two Sum',
      status: 'sent',
      error: null,
      message_url: 'https://discord.com/channels/1/2/3',
      created_at: '2026-11-28T08:00:00Z',
    };
    expect(fromDeliveries([post])[0]).toMatchObject({ kind: 'post', module: 'leetcode', href: post.message_url, link: undefined });
  });

  it('merges every source newest first, whatever form the time has', () => {
    const rows = mergeTimeline(
      fromAudit([entry({ created_at: '2026-11-28T09:30:00.500000+00:00' })]),
      fromNotifications([note({ at: '2026-11-28T10:00:00Z' }), note({ id: 'event-9', at: '2026-11-28T09:00:00Z' })]),
    );
    expect(rows.map((r) => r.id)).toEqual(['notification:event-1', 'audit:1', 'notification:event-9']);
  });
});
