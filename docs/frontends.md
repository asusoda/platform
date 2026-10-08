# Frontends

Platform has two officer frontends. `dashboard/` is the officer dashboard: one page for each org that shows what runs and what failed. `web/` is the older web app with the points, store, calendar, compute and Jeopardy pages, and the member store.

## Officer dashboard

`dashboard/` is a Vite and React app with Tailwind and TanStack Query. It calls the API and has no server code.

| Page | Shows |
| --- | --- |
| Overview | Problems, module switches, members, points, pods, agent use, CI, apps, alert feeds, sessions, recent changes and job runs |
| Compute | Pods and their sessions |
| Alerts | Feeds: create, pause, run now, delete |
| Apps | RunPod app deploys and their health |
| Agents | Conversation, memory and member counts. It shows no conversation text |
| CI | The latest GitHub Actions runs for the repos the org lists |
| Tokens | Machine tokens: create and revoke |
| Activity | The org's audit log, with pages |
| Settings | Branding, module switches and org secrets |

The dashboard uses these officer routes in `modules/dashboard/`:

| Route | Does |
| --- | --- |
| `GET /api/dashboard/<org>/overview` | Every section in one response |
| `GET /api/dashboard/<org>/ci` | The latest runs for each listed repo, kept in a cache for 120 seconds |
| `PUT /api/dashboard/<org>/ci/repos` | Sets the repo list: `{"repos": ["owner/name"]}`, 20 or fewer |
| `GET`, `PUT /api/dashboard/<org>/branding` | Gets or sets `logo_url` (https) and `accent_color` (`#RRGGBB`). An empty string or null removes a value |

For private repos, save a read-only GitHub token with Actions read access as the org secret `github_token`.

Each org sets its logo and accent color on the Settings page. The accent color sets the `--accent` CSS variable. Only primary buttons and the org initial use it. `--accent-fg` is black or white, for contrast. With no branding, the dashboard is gray and shows the first letter of the org name.

The dashboard uses the same type and colors as `site/`: Geist, Geist Mono and the gray tokens of the fumadocs-ui theme. The tokens are in `dashboard/src/index.css`. Light and dark follow the system; the switch at the bottom of the sidebar sets one.

`dashboard/src/components/ui.tsx` has the shared parts: `PageHeader`, `Card`, `Table`, `Button`, `Input`, `Select`, `Textarea`, `Badge`, `EmptyState` and the loading skeletons. Use them on a new page. Do not style a one-off control.

The landing page shows dashboard screenshots from `site/public/screenshots/`. After a UI change, run `npm run screenshots` in `dashboard/`. The script builds the dashboard, serves it with `vite preview` and answers each API call from `scripts/fixtures.mjs`, a fictional org. It needs Playwright with Chromium. If the Chromium version does not match Playwright, set `PLAYWRIGHT_CHROMIUM` to the browser binary.

Officers sign in at `/api/auth/login?client=dashboard`. After Discord, the API sends them to `DASHBOARD_URL/auth/` with a one-time code.

```bash
cd dashboard
cp .env.example .env     # VITE_API_URL=http://localhost:8000
npm install
npm run dev              # http://localhost:5173
npm test
npm run build            # dist/
```

To deploy the dashboard:

1. Host `dashboard/` as a static site. On Vercel, set the root folder to `dashboard`, the build to `npm run build` and the output to `dist`. Send every path to `index.html`.
2. Set `VITE_API_URL` to the API URL.
3. Set `DASHBOARD_URL` on the API to the dashboard URL. The API adds it to CORS and uses it for the sign-in return.

## Web app

`web/` is a Create React App project (React 19, pnpm, Tailwind and MUI). The `web` container serves the build with `serve` on port 5000.

```bash
cd web && pnpm install && pnpm start    # port 5000
npx react-scripts test --watchAll=false src/hooks src/utils
```

`REACT_APP_API_URL` goes into the bundle at build time. Its default is `https://api.thesoda.io`, the example SoDA server (`web/src/config.js`). A change needs a new build.

`web/src/App.js` has the routes:

- Open: `/`, `/login`, `/auth` (gets the tokens for the one-time code), `/store/:orgPrefix`, `/store/:orgPrefix/login`, `/500`, `/metrics`.
- Officer, behind `PrivateRoute`: `/select-organization`, `/superadmin`, and `/:orgPrefix/` with `dashboard`, `users`, `leaderboard`, `addpoints`, `calendar`, `storefront/...`, `transactions`, `compute`, `compute/:podId/files`, `panel`, `gamepanel`, `activegame` and `jeopardy`.
- Old paths without an org (`/home`, `/users` and others) go to `/select-organization`.

Use `useOrgNavigation()` from `web/src/hooks/` to make paths. Do not write a path with the org prefix by hand.

`web/src/components/auth/AuthContext.js` keeps `accessToken`, `refreshToken`, `user` and `currentOrg` in `localStorage`. `web/src/components/utils/axios.js` adds the `Authorization` header. On a 403 it calls `/api/auth/refresh` and sends the request again one time. If the refresh fails, it signs out.

`hooks/useOrgModules.js` reads `GET /api/organizations/<id>/modules`. The home page and the navigation bar hide the modules that the org turned off. If you type the URL of a hidden page, the page opens, but its API calls return 404.

The Jeopardy and bot pages (`ActiveGame`, `GamePanel`, `Jeopardy`, `BotControlPanel`, `AwardPanel`, `SetupButton`, `GameBoard`) call paths that the API does not have. [API contract](./api-contract.md) lists them.
