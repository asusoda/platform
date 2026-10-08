import { createGetUrl } from 'fumadocs-core/source';
import docSources from './doc-sources.generated.json';

export const appName = 'Platform';
export const docsRoute = '/docs';
export const docsImageRoute = '/og/docs';
export const docsContentRoute = '/llms.mdx/docs';

export const gitConfig = {
  user: 'theaisocietyasu',
  repo: 'bedrock',
  branch: 'main',
};

export const repoUrl = `https://github.com/${gitConfig.user}/${gitConfig.repo}`;

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
