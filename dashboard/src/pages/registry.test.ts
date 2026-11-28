// Every page has a docs page that exists and one short line of description, so each header has a Docs link.
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { ADMIN_PAGES } from './admin/registry';
import { PAGES } from './registry';

const ROOT = resolve(__dirname, '../../..');
const DOCS = resolve(ROOT, 'docs');
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

// The switch keys of the API: OPTIONAL_MODULES in modules/organizations/service.py and each <module>.<name> of
// SUBMODULES in modules/manifest.py.
function switchKeys(): string[] {
  const block = (file: string, name: string) => {
    const text = readFileSync(resolve(ROOT, file), 'utf8');
    return text.slice(text.indexOf(`${name} = {`), text.indexOf('\n}\n', text.indexOf(`${name} = {`)));
  };
  const modules = [...block('modules/organizations/service.py', 'OPTIONAL_MODULES').matchAll(/^ {4}"([a-z_]+)":/gm)].map((m) => m[1]);
  const subs = [...block('modules/manifest.py', 'SUBMODULES').matchAll(/^ {4}"([a-z_]+)": \(([^)]*)\)/gm)].flatMap((m) =>
    [...m[2].matchAll(/"([a-z_]+)"/g)].map((n) => `${m[1]}.${n[1]}`),
  );
  return [...modules, ...subs];
}

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

  it('gates pages by switch keys that the API has', () => {
    const keys = switchKeys();
    expect(keys).toContain('points.store');
    for (const page of PAGES) {
      for (const module of [page.module ?? []].flat()) expect(keys, page.path).toContain(module);
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
