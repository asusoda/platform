import { createMDX } from 'fumadocs-mdx/next';

const withMDX = createMDX();

// Docs pages that were merged into other pages keep their old URLs.
const movedDocs = {
  '/docs/codebase/backend-modules': '/docs/codebase/architecture',
  '/docs/codebase/api-reference': '/docs/codebase/api-contract',
  '/docs/codebase/discord-bot': '/docs/codebase/architecture',
  '/docs/codebase/frontend': '/docs/codebase/frontends',
  '/docs/codebase/deployment-and-operations': '/docs/codebase/operations',
  '/docs/codebase/gotchas': '/docs/project/roadmap',
  '/docs/modules/dashboard': '/docs/codebase/frontends',
  '/docs/modules/hermes': '/docs/codebase/operations',
  '/docs/modules/tools-and-mcp': '/docs/codebase/architecture',
  '/docs/project/runpod-deploy': '/docs/codebase/getting-started',
};

/** @type {import('next').NextConfig} */
const config = {
  reactStrictMode: true,
  async redirects() {
    return Object.entries(movedDocs).map(([source, destination]) => ({ source, destination, permanent: true }));
  },
};

export default withMDX(config);
