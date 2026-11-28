import { describe, expect, it } from 'vitest';
import { matches, moduleLabel, notificationModule } from './modules';
import type { CatalogModule } from './types';

const points: CatalogModule = {
  name: 'points',
  title: 'Points',
  description: 'Points and event check-ins.',
  category: 'Members',
  parent: null,
  switchable: true,
  enabled: true,
  ready: true,
  needs: [{ key: 'discord', label: 'Discord bot', kind: 'integration', optional: false, connected: true }],
  submodules: [{ key: 'points.store', title: 'Store', description: 'Merch paid with points', shared: false, enabled: true }],
  shared_content: [{ name: 'asu', key: 'knowledge.asu', title: 'ASU', description: 'Campus pages' }],
  limits: [],
};

describe('matches', () => {
  it('matches every module when the search is empty', () => {
    expect(matches(points, '  ')).toBe(true);
  });

  it('matches the title, the category, a need, a sub-module and shared content, with no case', () => {
    expect(matches(points, 'poin')).toBe(true);
    expect(matches(points, 'MEMBERS')).toBe(true);
    expect(matches(points, 'discord')).toBe(true);
    expect(matches(points, 'store')).toBe(true);
    expect(matches(points, 'asu')).toBe(true);
  });

  it('does not match other text', () => {
    expect(matches(points, 'leetcode')).toBe(false);
  });

  it('matches a layer, which has no category', () => {
    expect(matches({ ...points, name: 'hosting', title: 'Hosting', category: null }, 'host')).toBe(true);
  });
});

describe('module names', () => {
  it('names the sub-modules and the old keys of older notifications', () => {
    expect(moduleLabel('points.store')).toBe('Store');
    expect(moduleLabel('bot.leetcode')).toBe('LeetCode');
    expect(notificationModule('order')).toBe('points.store');
    expect(notificationModule('apps')).toBe('hosting');
  });
});
