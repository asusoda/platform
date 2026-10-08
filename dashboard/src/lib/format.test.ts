import { describe, expect, it } from 'vitest';
import { compact, deployTone, runTone, timeAgo } from './format';

describe('timeAgo', () => {
  const now = new Date('2026-10-08T12:00:00Z');
  it('reads naive timestamps as UTC', () => {
    expect(timeAgo('2026-10-08T11:00:00', now)).toBe('1h ago');
    expect(timeAgo('2026-10-08T11:59:30Z', now)).toBe('30s ago');
    expect(timeAgo('2026-10-10T12:00:00Z', now)).toBe('in 2d');
    expect(timeAgo(null, now)).toBe('never');
  });
});

describe('tones', () => {
  it('maps run and deploy states', () => {
    expect(runTone('in_progress', null)).toBe('accent');
    expect(runTone('completed', 'success')).toBe('ok');
    expect(runTone('completed', 'failure')).toBe('bad');
    expect(deployTone('failed')).toBe('bad');
    expect(compact(1250)).toBe('1.3K');
  });
});
