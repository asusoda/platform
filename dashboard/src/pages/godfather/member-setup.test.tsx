import { describe, expect, it } from 'vitest';
import { setupBody } from './member-setup';

describe('member setup body', () => {
  it('is null when both fields are empty, so the pod has no setup', () => {
    expect(setupBody({ repo: ' ', script: '\n' })).toBeNull();
  });

  it('trims the repo and keeps the script as typed', () => {
    expect(setupBody({ repo: ' https://github.com/org/w.git ', script: 'make\n' })).toEqual({
      repo: 'https://github.com/org/w.git',
      script: 'make\n',
    });
  });
});
