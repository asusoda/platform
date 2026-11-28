// Every page has a docs page that exists and one short line of description, so each header has a Docs link.
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { ADMIN_PAGES } from './admin/registry';
import { PAGES } from './registry';

const DOCS = resolve(__dirname, '../../../docs');
const SITE_PAGES = resolve(__dirname, '../../../site/content/docs');

// The file in the repo that a docs page of the site comes from, as site/scripts/sync-docs.ts maps them.
function docsFile(page: string): string {
  const [section, slug] = page.split('/');
  if (!slug) return resolve(SITE_PAGES, `${section}.mdx`);
  return section === 'modules' ? resolve(DOCS, 'modules', `${slug}.md`) : resolve(DOCS, `${slug}.md`);
}

// The anchor that the docs site gives a heading.
const anchor = (heading: string) =>
  heading
    .toLowerCase()
    .replace(/[^a-z0-9 -]/g, '')
    .trim()
    .replace(/ +/g, '-');

const entries = [...PAGES.map((p) => ({ space: 'org', ...p })), ...ADMIN_PAGES.map((p) => ({ space: 'admin', ...p }))];

describe('page registry', () => {
  it.each(entries.map((e) => [`${e.space} ${e.path || 'home'}`, e] as const))('%s links a docs page that exists', (_, e) => {
    const [page, hash] = e.docs.split('#');
    const file = docsFile(page);
    expect(existsSync(file), file).toBe(true);
    if (hash) {
      const headings = readFileSync(file, 'utf8')
        .split('\n')
        .filter((line) => line.startsWith('#'))
        .map((line) => anchor(line.replace(/^#+/, '')));
      expect(headings).toContain(hash);
    }
  });

  it('gives each sidebar page one short line of description', () => {
    for (const e of entries.filter((x) => !('hidden' in x && x.hidden) && x.path)) {
      expect(e.description, e.path).toBeTruthy();
      expect(e.description!.length, e.path).toBeLessThanOrEqual(60);
      expect(e.description!.split('. ').length, e.path).toBe(1);
    }
  });
});
