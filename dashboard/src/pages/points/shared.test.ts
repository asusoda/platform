import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import type { PointsMember } from '../../lib/types';
import { addToTotals, groupEntries, type MembersBody, memberChanges, refreshPoints } from './shared';

describe('memberChanges', () => {
  const member = { name: 'Ada', asu_id: null, academic_standing: 'Junior', major: null };

  it('sends no field that did not change', () => {
    expect(memberChanges(member, { name: 'Ada', asu_id: '', academic_standing: 'Junior', major: '' })).toEqual({});
  });

  it('sends a changed field, and null for a field made empty', () => {
    expect(memberChanges(member, { name: 'Ada', asu_id: '1234', academic_standing: '', major: '' })).toEqual({
      asu_id: '1234',
      academic_standing: null,
    });
  });

  it('treats whitespace as empty and ignores padding', () => {
    expect(memberChanges(member, { name: ' Ada ', asu_id: '', academic_standing: '   ', major: '' })).toEqual({
      academic_standing: null,
    });
  });
});

const person = (id: number, email: string, points: number) => ({ id, uuid: `u-${id}`, email, username: null, points }) as PointsMember;

describe('addToTotals', () => {
  it('adds the points to each awarded member in the cached list, found by email in any case', () => {
    const client = new QueryClient();
    client.setQueryData<MembersBody>(['points', 'soda', 'members'], { total_users: 2, users: [person(1, 'ada@asu.edu', 10), person(2, 'bo@asu.edu', 5)] });
    addToTotals(client, 'soda', ['ADA@asu.edu'], 7);
    expect(client.getQueryData<MembersBody>(['points', 'soda', 'members'])?.users.map((m) => m.points)).toEqual([17, 5]);
  });
});

describe('refreshPoints', () => {
  it('marks every page with a points total of the org as stale, and no other org', () => {
    const client = new QueryClient();
    for (const key of [['points', 'soda', 'members'], ['overview', 'soda'], ['store', 'soda', 'orders'], ['member-store', 'soda', 'profile'], ['points', 'ais', 'members']])
      client.setQueryData(key, {});
    refreshPoints(client, 'soda');
    const stale = client.getQueryCache().getAll().filter((q) => q.isStale()).map((q) => q.queryKey.join('/'));
    expect(stale.sort()).toEqual(['member-store/soda/profile', 'overview/soda', 'points/soda/members', 'store/soda/orders']);
  });
});

describe('groupEntries', () => {
  it('puts a purchase and its refund in one order group, apart from an event of the same day', () => {
    const e = (id: number, points: number, event: string | null, timestamp: string) => ({ id, points, event, awarded_by_officer: null, timestamp, last_updated: null });
    const groups = groupEntries([e(1, -30, 'Storefront Purchase - Order #7', '2026-10-02'), e(2, 30, 'Refund - Order #7', '2026-10-03'), e(3, 5, null, '2026-10-01')]);
    expect(groups.map((g) => [g.label, g.order, g.total])).toEqual([
      ['Order #7', 7, 0],
      ['No event', null, 5],
    ]);
  });
});
