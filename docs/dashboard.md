# Dashboard

`dashboard/` is the officer dashboard: one page per org that shows what is running and what failed. It is a Vite and React app that talks to the API. The older `web/` admin app stays as it is.

## Pages

| Page | Shows |
| --- | --- |
| Overview | Problems, module switches, members, points, pods, agent use, CI, apps, alert feeds, upcoming sessions, recent changes and job runs |
| Compute | Pods and scheduled sessions |
| Alerts | Feeds: create, pause, run now, delete |
| Apps | RunPod app deploys and their health |
| Agents | Conversation, memory and member counts. No conversation text. |
| CI | Latest GitHub Actions runs for the repos the org lists |
| Tokens | Machine tokens: create and revoke |
| Activity | The org's audit log, paged |
| Settings | Module switches and org secrets |

Agents such as SparkyAI and godfather show up through what they use: their tokens, their conversations in `agents`, pods in `compute`, apps in `runpod`.

## API

Officer routes, in `modules/dashboard/`:

| Route | What it does |
| --- | --- |
| `GET /api/dashboard/<org>/overview` | Every section in one response |
| `GET /api/dashboard/<org>/ci` | Latest runs per listed repo, cached 120 seconds |
| `PUT /api/dashboard/<org>/ci/repos` | Set the repo list, `{"repos": ["owner/name"]}`, at most 20 |

Private repos need an org secret named `github_token` (a read-only token with Actions read access).

## Sign-in

The dashboard sends officers to `/api/auth/login?client=dashboard`. After Discord, the API returns them to `DASHBOARD_URL/auth/` with a one-time code, which the dashboard exchanges for tokens.

## Running it

```bash
cd dashboard
cp .env.example .env     # VITE_API_URL=http://localhost:8000
npm install
npm run dev              # http://localhost:5173
npm test
npm run build            # dist/
```

## Deploying

1. Host `dashboard/` as a static site, for example on Vercel with root directory `dashboard`, build `npm run build`, output `dist`. Set `VITE_API_URL` to the API URL. Route every path to `index.html`.
2. Set `DASHBOARD_URL` on the API to the dashboard's URL. It is added to CORS and used for the sign-in return.
3. Open the CI page and list the org's repos.
