import { describe, expect, it } from 'vitest';
import { compact, deployTone, duration, keyPath, podTone, runTone, timeAgo } from './format';

describe('duration', () => {
  it('shows hours and minutes', () => {
    expect(duration('2026-10-08T18:00:00Z', '2026-10-08T20:00:00Z')).toBe('2h');
    expect(duration('2026-10-08T18:00:00', '2026-10-08T19:30:00Z')).toBe('1h 30m');
    expect(duration('2026-10-08T18:00:00Z', '2026-10-08T18:45:00Z')).toBe('45m');
    expect(duration('2026-10-08T18:00:00Z', '2026-10-08T17:00:00Z')).toBe('0m');
  });
});

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
    expect(runTone('in_progress', null)).toBe('active');
    expect(runTone('completed', 'success')).toBe('ok');
    expect(runTone('completed', 'failure')).toBe('bad');
    expect(deployTone('failed')).toBe('bad');
    expect(compact(1250)).toBe('1.3K');
  });
});

describe('keyPath', () => {
  it('encodes each segment and keeps the slashes', () => {
    expect(keyPath('docs/getting started')).toBe('docs/getting%20started');
    expect(keyPath('faq:club?')).toBe('faq%3Aclub%3F');
    expect(podTone('RUNNING')).toBe('ok');
  });
});
