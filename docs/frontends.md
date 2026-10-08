# Frontends

Platform has two officer frontends. `dashboard/` is the officer dashboard: officers see and control what each org runs. `web/` is the older web app with the points, store, calendar, compute and Jeopardy pages, and the member store.

## Officer dashboard

`dashboard/` is a Vite and React app with Tailwind and TanStack Query. It calls the API and has no server code.

| Page | Shows |
| --- | --- |
| Overview | Problems, module switches, members, points, pods, agent use, CI, apps, alert feeds, sessions, recent changes and job runs |
| Compute | Pods with their live RunPod status: create, start, stop, restart, terminate, who can connect, sessions and files |
| Alerts | Feeds: create, pause, run now, delete, and the history of each feed: its last 50 runs with counts and errors, and its last 50 items |
| Apps | The org's bots, agents, sites and services, grouped by kind, with the host of each: register a manifest or repo, see the pod and deployments, deploy a tag with a dry-run preview, roll back, delete |
| Knowledge | Source packs to add or sync, sources filtered by domain: add, edit, pause and run crawls, delete sources, and test a search |
| Agents | Conversation, memory and member counts. It shows no conversation text |
| Tokens | Machine tokens: create and revoke |
| Activity | Two tabs: Changes, the org's audit log with pages; CI runs, the latest GitHub Actions runs for the repos the org lists |
| Settings | General, branding, module switches, calendar, LeetCode and org secrets |
| Superadmin | Orgs, officer roles, Discord servers without an org, and the audit log of all orgs. Only the superadmin sees it |

The dashboard uses these officer routes in `modules/dashboard/`:

| Route | Does |
| --- | --- |
| `GET /api/dashboard/<org>/overview` | Every section in one response |
| `GET /api/dashboard/<org>/ci` | The latest runs for each listed repo, kept in a cache for 120 seconds |
| `PUT /api/dashboard/<org>/ci/repos` | Sets the repo list: `{"repos": ["owner/name"]}`, 20 or fewer |
| `GET`, `PUT /api/dashboard/<org>/branding` | Gets or sets `logo_url` (https), `accent_color` (`#RRGGBB`) and `website_url` (https). An empty string or null removes a value |
| `/api/dashboard/<org>/apps/...` | List, register, delete, deploy and roll back apps, and read the pod. The same operations as `/api/apps` in [runpod-apps](modules/runpod-apps.md), for officers |
| `/api/dashboard/<org>/knowledge/...` | List and delete sources, add and run crawls, and search. The same operations as `/api/knowledge` in [knowledge](modules/knowledge.md), for officers. The sources list also says if the org may publish public sources |

The other pages use the routes of their modules: `/api/compute`, `/api/alerts`, `/api/organizations` and `/api/superadmin`.

For private repos, save a read-only GitHub token with Actions read access as the org secret `github_token`.

The Settings page has these sections: General (description, points per message, points cooldown), Branding, Modules, Calendar and LeetCode (shown only when the module is on), and Secrets. The officer role shows there read-only. The Superadmin page shows only to the superadmin: it sets an org's officer role, adds an org for a Discord server the bot is in, removes an org, and shows the audit log of all orgs. It uses the `/api/superadmin/` routes. When the bot is not available, those routes return 503 and the page says so.

Each org sets its logo, accent color and website on the Settings page. The sidebar links to the website. The accent color sets the `--accent` CSS variable. Only primary buttons and the org initial use it. `--accent-fg` is black or white, for contrast. With no branding, the dashboard is gray and shows the first letter of the org name.

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
