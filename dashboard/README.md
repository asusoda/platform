# Dashboard

Officer dashboard for Platform: overview, compute, alerts, apps, agents, CI, tokens, activity and settings for one org. Vite, React, Tailwind and TanStack Query.

```bash
cp .env.example .env   # VITE_API_URL
npm install
npm run dev
npm test
npm run build
```

`src/lib/` holds the API client, sign-in and queries. `src/pages/` has one file per page. `src/components/ui.tsx` has the shared parts.

See [docs/dashboard.md](../docs/dashboard.md) for routes, sign-in and deployment.
