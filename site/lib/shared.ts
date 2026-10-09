import { createGetUrl } from 'fumadocs-core/source';
import docSources from './doc-sources.generated.json';

export const appName = 'Platform';
export const docsRoute = '/docs';
export const docsImageRoute = '/og/docs';
export const docsContentRoute = '/llms.mdx/docs';

/** The repo that holds the docs pages, for the source link of each page. */
export const gitConfig = {
  user: 'theaisocietyasu',
  repo: 'bedrock',
  branch: 'main',
};

/** The original repo of Platform, by SoDA. LICENSE clause 4b requires a link to it. */
export const repoUrl = 'https://github.com/asusoda/platform';

const getContentUrl = createGetUrl(docsContentRoute);

export function getPageMarkdownUrl(page: { slugs: string[]; locale?: string }) {
  const segments = [...page.slugs, 'content.md'];

  return { segments, url: getContentUrl(segments, page.locale) };
}

const getImageUrl = createGetUrl(docsImageRoute);

export function getPageImageUrl(page: { slugs: string[]; locale?: string }) {
  const segments = [...page.slugs, 'image.png'];

  return { segments, url: getImageUrl(segments, page.locale) };
}

/** Repository path of a docs page: pages copied from docs/ link to their source file. */
export function repoPath(pagePath: string): string {
  const sources: Record<string, string> = docSources;
  return sources[pagePath] ?? `site/content/docs/${pagePath}`;
}
