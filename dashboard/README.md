# Dashboard

Officer dashboard for Platform: the pages officers use to see and control one org, and a Superadmin page for the superadmin. Vite, React, Tailwind and TanStack Query.

```bash
cp .env.example .env   # VITE_API_URL
npm install
npm run dev
npm test
npm run build          # tsc, then vite build to dist/
npm run screenshots    # images for the landing page, see docs/frontends.md
```

## Layout

```
src/
  main.tsx, app.tsx        start the app; app.tsx makes the routes from pages/registry.tsx
  index.css                theme tokens
  components/
    ui.tsx                 shared parts: buttons, cards, tables, fields, dialogs, notes
    tabs.tsx               TabBar and useTabParam
    module-gate.tsx        the note for a module that is off
    shell.tsx              sidebar and page frame; the sidebar comes from pages/registry.tsx
    activity-list.tsx, org-mark.tsx, logo.tsx
  lib/
    api.ts, auth.ts        API client and sign-in tokens
    queries.ts             queries that two or more pages use
    format.ts, branding.ts, theme.ts, org.ts
    types/                 API response shapes, one file for each domain
  pages/
    registry.tsx           every org page: path, label, icon, section, module, component
    <page>.tsx             a small page
    <page>/index.tsx       a large page; the other files in the folder are its parts
scripts/
  fixtures.mjs             API responses for a fictional org
  screenshots.mjs          screenshots for the landing page
```

To add a page, write the page file and add one entry to `PAGES` in `src/pages/registry.tsx`. See [docs/frontends.md](../docs/frontends.md) for all the steps, the routes, sign-in and deployment.
