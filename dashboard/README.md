# Dashboard

Officer dashboard for Platform: overview, compute, alerts, apps, agents, CI, tokens, activity and settings for one org, and a Superadmin page for the superadmin. Vite, React, Tailwind and TanStack Query.

```bash
cp .env.example .env   # VITE_API_URL
npm install
npm run dev
npm test
npm run build
npm run screenshots   # images for the landing page, see docs/frontends.md
```

`src/lib/` holds the API client, sign-in and queries. `src/pages/` has one file per page; `src/pages/settings/` has one file per Settings section. `src/components/ui.tsx` has the shared parts. `scripts/` has the screenshot script and its fixtures.

See [docs/frontends.md](../docs/frontends.md) for routes, sign-in and deployment.
