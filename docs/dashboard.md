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
| Settings | Branding, module switches and org secrets |

Agents and CLIs show up through what they use: their tokens, their conversations in `agents`, pods in `compute`, apps in `runpod`.

## API

Officer routes, in `modules/dashboard/`:

| Route | What it does |
| --- | --- |
| `GET /api/dashboard/<org>/overview` | Every section in one response |
| `GET /api/dashboard/<org>/ci` | Latest runs per listed repo, cached 120 seconds |
| `PUT /api/dashboard/<org>/ci/repos` | Set the repo list, `{"repos": ["owner/name"]}`, at most 20 |
| `GET /api/dashboard/<org>/branding` | The org's `{"logo_url", "accent_color"}`, each null when unset |
| `PUT /api/dashboard/<org>/branding` | Set either or both; an empty string or null clears one |

Private repos need an org secret named `github_token` (a read-only token with Actions read access).

## Branding

Each org sets its own logo and accent color on the Settings page. The sidebar shows the org's logo and name; the accent color sets the `--accent` CSS variable. Only primary buttons and the org initial use it. `--accent-fg` is black or white, whichever reads better on it. With nothing set the dashboard is neutral grey and shows the org's initial. `logo_url` must be an https URL; `accent_color` must be `#RRGGBB`. Both are stored under `branding` in the org's config. The overview response carries them in `organization.branding`.

## Design

The dashboard uses the same type and colors as `site/`: Geist and Geist Mono, and the neutral grays of the fumadocs-ui theme. The tokens are in `dashboard/src/index.css`. Light and dark follow the system; the switch at the bottom of the sidebar sets either one.

`dashboard/src/components/ui.tsx` has the shared parts: `PageHeader`, `Card`, `Table`, `Button`, `Input`, `Select`, `Textarea`, `Badge`, `EmptyState` and the loading skeletons. Use them on a new page; do not style a one-off control.

## Screenshots

The landing page shows screenshots of the dashboard from `site/public/screenshots/`. To make them again after a UI change:

```bash
cd dashboard
npm run screenshots
```

The script builds the dashboard, serves it with `vite preview` and answers every API call from `scripts/fixtures.mjs`, a fictional org. It needs Playwright with Chromium, from a global install or `npm i --no-save playwright`. If the installed Chromium does not match the Playwright version, set `PLAYWRIGHT_CHROMIUM` to the browser binary.

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
