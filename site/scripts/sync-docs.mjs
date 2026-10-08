// Copies the repo's docs/*.md into content/docs as MDX, so docs/ stays the only source.
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoDocs = path.resolve(here, '../../docs');
const out = path.resolve(here, '../content/docs');

const sections = {
  modules: {
    title: 'Modules',
    pages: [
      ['compute.md', 'compute'],
      ['agents.md', 'agents'],
      ['knowledge.md', 'knowledge'],
      ['asu.md', 'asu'],
      ['accounts.md', 'accounts'],
      ['alerts.md', 'alerts'],
      ['runpod-apps.md', 'runpod-apps'],
      ['tools-and-mcp.md', 'tools-and-mcp'],
    ],
  },
  codebase: {
    title: 'Codebase',
    pages: [
      ['01-getting-started.md', 'getting-started'],
      ['02-architecture.md', 'architecture'],
      ['03-data-model.md', 'data-model'],
      ['04-authentication.md', 'authentication'],
      ['05-backend-modules.md', 'backend-modules'],
      ['writing-a-module.md', 'writing-a-module'],
      ['06-api-reference.md', 'api-reference'],
      ['07-discord-bot.md', 'discord-bot'],
      ['08-frontend.md', 'frontend'],
      ['09-deployment-and-operations.md', 'deployment-and-operations'],
      ['10-gotchas-and-known-issues.md', 'gotchas'],
      ['api-contract.md', 'api-contract'],
    ],
  },
  project: {
    title: 'Project',
    pages: [
      ['runpod-deploy.md', 'runpod-deploy'],
      ['roadmap.md', 'roadmap'],
    ],
  },
};

const routes = new Map();
for (const [section, { pages }] of Object.entries(sections)) {
  for (const [file, slug] of pages) routes.set(file, `/docs/${section}/${slug}`);
}
routes.set('README.md', '/docs');

function rewriteLink(target) {
  if (/^[a-z]+:/i.test(target) || target.startsWith('#')) return target;
  const [file, hash] = target.replace(/^\.\//, '').split('#');
  const route = routes.get(file);
  if (route) return hash ? `${route}#${hash}` : route;
  return `https://github.com/asusoda/platform/blob/main/${path.posix.join('docs', target)}`;
}

function escapeText(text) {
  return text
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\{/g, '&#123;')
    .replace(/\}/g, '&#125;');
}

function convertLine(line) {
  const parts = line.split(/(`+[^`]*`+)/);
  return parts
    .map((part, i) => {
      if (i % 2 === 1) return part;
      const links = [];
      const withTokens = part.replace(/\]\(([^)\s]+)\)/g, (_, target) => {
        links.push(rewriteLink(target));
        return `](\u0000${links.length - 1}\u0000)`;
      });
      return escapeText(withTokens).replace(/\u0000(\d+)\u0000/g, (_, n) => links[Number(n)]);
    })
    .join('');
}

function toMdx(markdown) {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  let title = '';
  let fence = null;
  const body = [];
  for (const line of lines) {
    const opener = line.match(/^\s*(```+|~~~+)/);
    if (fence) {
      body.push(line);
      if (opener && opener[1].startsWith(fence)) fence = null;
      continue;
    }
    if (opener) {
      fence = opener[1];
      body.push(line);
      continue;
    }
    if (!title && line.startsWith('# ')) {
      title = line.slice(2).replace(/^\d+\.\s*/, '').trim();
      continue;
    }
    body.push(line.startsWith('    ') ? line : convertLine(line));
  }
  const front = `---\ntitle: ${JSON.stringify(title)}\n---\n`;
  return `${front}\n${body.join('\n').trim()}\n`;
}

const sourcesMap = {};
for (const [section, { title, pages }] of Object.entries(sections)) {
  for (const [file, slug] of pages) sourcesMap[`${section}/${slug}.mdx`] = `docs/${file}`;
  const dir = path.join(out, section);
  await rm(dir, { recursive: true, force: true });
  await mkdir(dir, { recursive: true });
  for (const [file, slug] of pages) {
    const source = await readFile(path.join(repoDocs, file), 'utf8');
    await writeFile(path.join(dir, `${slug}.mdx`), toMdx(source));
  }
  await writeFile(
    path.join(dir, 'meta.json'),
    `${JSON.stringify({ title, pages: pages.map(([, slug]) => slug) }, null, 2)}\n`,
  );
}

await writeFile(
  path.resolve(here, '../lib/doc-sources.generated.json'),
  `${JSON.stringify(sourcesMap, null, 2)}\n`,
);
