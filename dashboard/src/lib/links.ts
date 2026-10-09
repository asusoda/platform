// Links to the Platform repo, its docs and its landing page.

// The original repo of Platform, by SoDA. LICENSE clause 4b requires a link to it.
export const SOURCE_URL = 'https://github.com/asusoda/platform';

// The repo that holds the docs and packs.
export const REPO_URL = SOURCE_URL;

// The URL of the site/ deployment. Without it, the links go to the docs and README in the repo.
const SITE_URL = (import.meta.env.VITE_SITE_URL as string | undefined)?.replace(/\/$/, '') || null;

export const DOCS_URL = SITE_URL ? `${SITE_URL}/docs` : `${REPO_URL}/tree/main/docs`;
export const ABOUT_URL = SITE_URL ?? `${REPO_URL}#readme`;

// background is the fill of the mark. The logos have fixed colors, so it does not follow the theme.
export type BuiltBy = { name: string; short: string; url: string; logo: string; background: string };

// The orgs that build Platform, in the order of the marks. To add an org, add one line and put its logo in public/orgs/.
export const BUILT_BY: BuiltBy[] = [
  {
    name: 'The AI Society at ASU',
    short: 'AI Society',
    url: 'https://ais-asu.com',
    logo: 'orgs/ais.svg',
    background: '#0a0a0a',
  },
  {
    name: 'Software Developers Association at ASU',
    short: 'SoDA',
    url: 'https://thesoda.io',
    logo: 'orgs/soda.svg',
    background: '#ffffff',
  },
];

// The names with commas between them and "and" before the last one.
export function joinNames(names: string[]): string {
  return names.length < 2 ? (names[0] ?? '') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

// The label of the marks. The short form leaves out the school.
export const builtByLabel = (orgs: BuiltBy[] = BUILT_BY, short = false) =>
  `Built by ${joinNames(orgs.map((o) => o.short))}${short ? '' : ' at ASU'}`;

// A page of the docs, such as modules/calendar.
export const docsPage = (path: string) => (SITE_URL ? `${SITE_URL}/docs/${path}` : `${REPO_URL}/blob/main/docs/${path}.md`);
