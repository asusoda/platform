# Frontends

Platform has one frontend, `dashboard/`. Officers use it to see and control what each org runs. Members use its store pages, `/store/<org>`.

## Officer dashboard

`dashboard/` is a Vite and React app with Tailwind and TanStack Query. It calls the API and has no server code.

The sidebar puts the pages in sections: Members (Points, Store), Automations, Knowledge and MCP (Knowledge, MCP), and Infrastructure (Hosting, Tokens). Automations has a group for each kind:

- Webhooks: Webhooks, Alerts.
- Scheduled jobs: Calendar sync.
- Bots: LeetCode.

`dashboard/src/pages/registry.tsx` has one entry for each page, with its section and group. To add an automation, add its page there with `group` set to `webhooks`, `scheduled` or `bots`. To add a kind, add a line to `GROUPS`.

The sidebar hides the page of an optional module when the module is off for the org. It hides Hosting only when the `runpod` and `compute` modules are both off. A section or group with no pages has no header. If you open the Points, Store, Calendar sync or LeetCode page while its module is off, the page links to Settings, Modules. The old path `agents` opens `mcp`, and `ci` opens Activity, CI runs. The old paths `apps` and `compute` open the Services and Member pods tabs of Hosting.

The sidebar collapses to a 56px rail of icons. To collapse or expand it, use the button at the left of the top bar, Ctrl+B (Cmd+B on a Mac) or `[`. The `[` key does nothing while you type in a field. The rail shows a tooltip with the page name on hover and on keyboard focus. The dashboard keeps the state in `localStorage` as `platform.sidebar`. On a phone, the sidebar is a menu that opens from the top bar.

The top bar above each page shows where the page is: Org / Section / Group / Page. A page with no group has no group crumb. Each page starts with `PageHeader`: the title is the sidebar label of the page, then one line of description, and the page actions on the right.

Lists that can be long (knowledge sources, points members and events, knowledge runs, store orders) show 100 rows, or 50 runs, and a button that shows more. A search field filters with `useDeferredValue`, so typing does not wait for the list. The audit log rows use `content-visibility: auto`.

The dashboard has one React Query client, made in `dashboard/src/lib/query-client.ts`. An answer is fresh for 30 seconds and stays in memory for 10 minutes after no page shows it, so a page opened again shows its data at once. A window focus does not refetch; pages with live data poll with `refetchInterval`. A list with a filter keeps the previous rows while the next ones load (`keepPreviousData`). The cache is in memory only, because answers hold member details; sign out clears it. A page entry in `registry.tsx` can have `prefetch`: the sidebar calls it on hover or keyboard focus, and the shell calls it when the page opens, so a gated page does not wait for its module check before it asks for its data. When requests fail together on an expired access token, they wait for one refresh.

| Page | Shows |
| --- | --- |
| Overview | A link to open notifications, module switches, members, points, pods, agent use, CI, services, alert feeds, sessions, recent changes and job runs |
| Integrations | The accounts and services the org connects, in two groups: state, keys, Test and the modules that use each one. See [integrations.md](./integrations.md) |
| Notifications | Problems that need an officer: failed alert runs, failed deploys, knowledge sources that could not be fetched. Resolve or reopen each one. The bell in the top bar shows the open count and the newest ones |
| Points | Members ranked by points, with the entries of each member. Award points to a member by email, username or Discord user ID. Upload an event check-in CSV. Events grouped by name, with delete for all entries of an event |
| Store | Products: add, edit (name, category, price in points, stock, image URL, description) and delete. Orders: change the status, add a message to the member, delete |
| Calendar sync | The Notion database and Google calendar settings, sync on or off, sync now, create the Google calendar, and the upcoming events |
| LeetCode | The daily post settings (channel, role to ping, time) and the slash commands members use |
| Compute | Pods with their live RunPod status: create, start, stop, restart, terminate, who can connect, sessions and files |
| Webhooks | The org's outbound webhooks: add, edit, turn on or off, send test, delete. Each has a name, a destination (Discord), the events it sends and the result of its last message. The alert feeds show below with a link to Alerts. See [webhooks.md](./webhooks.md) |
| Alerts | Feeds: create, pause, run now, delete, and the history of each feed: its last 50 runs with counts and errors, and its last 50 items |
| Hosting | What the org runs on RunPod, in two tabs. Each tab shows only when its module is on. Services (`?tab=services`, `runpod` module): the org's bots, agents, sites and services, grouped by kind, with the host of each. Register a manifest or repo, see the pod and deployments, deploy a tag with a dry-run preview, roll back, delete. Member pods (`?tab=pods`, `compute` module): the pods that members connect to, with their live RunPod status. Create, start, stop, restart, terminate, change who can connect, sessions, files and pod settings |
| Knowledge | Packs to add or sync, sources filtered by domain: upload documents one at a time or in a batch, add, edit, pause and run crawls, delete sources, change the passage size and search settings, and test a search |
| MCP | How to connect an agent to the MCP server, agent tokens, linked accounts, and conversation, memory and member counts. It shows no conversation text |
| Tokens | Machine tokens: create and revoke |
| Activity | Four tabs: Changes, the org's audit log with pages; Knowledge runs, the last crawls and uploads with their errors; CI runs, the latest GitHub Actions runs for the repos the org lists; Errors, the org's errors from the error log with Resolve, Reopen and the stack trace. Activity only shows data: webhooks are on the Webhooks page |
| Settings | General, branding, module switches and org secrets |
| Superadmin | Orgs, officer roles, Discord servers without an org, the audit log of all orgs, and the errors of every org and of the server. Only the superadmin sees it |

The dashboard uses these officer routes in `modules/dashboard/`:

| Route | Does |
| --- | --- |
| `GET /api/dashboard/<org>/overview` | Every section in one response |
| `GET /api/dashboard/<org>/trends?days=30` | One series per chart, a value per UTC day (7 to 90 days). Modules that are off have no series |
| `GET /api/dashboard/<org>/ci` | The latest runs for each listed repo, kept in a cache for 120 seconds |
| `PUT /api/dashboard/<org>/ci/repos` | Sets the repo list: `{"repos": ["owner/name"]}`, 20 or fewer |
| `GET`, `PUT /api/dashboard/<org>/branding` | Gets or sets `logo_url` (https), `accent_color` (`#RRGGBB`) and `website_url` (https). An empty string or null removes a value |
| `/api/dashboard/<org>/webhooks/...` | List, add, change, delete and test outbound webhooks. See [webhooks.md](./webhooks.md) |
| `/api/dashboard/<org>/apps/...` | List, register, delete, deploy and roll back apps, and read the pod. The same operations as `/api/apps` in [runpod-apps](modules/runpod-apps.md), for officers |
| `/api/dashboard/<org>/knowledge/...` | List and delete sources, upload documents, add and run crawls, read and set the search settings, start a reindex, read the run log, and search. The same operations as `/api/knowledge` in [knowledge](modules/knowledge.md), for officers. The sources list also says if the org may publish public sources |

The other pages use the routes of their modules: `/api/points`, `/api/storefront`, `/api/calendar`, `/api/compute`, `/api/alerts`, `/api/organizations` and `/api/superadmin`.

For private repos, connect GitHub on the Integrations page with a read-only token that can read Actions.

The Settings page has these sections: General (description, points per message, points cooldown), Branding, Modules and Secrets. The calendar and LeetCode settings are on the Calendar sync and LeetCode pages. The old links `settings#calendar` and `settings#leetcode` open those pages. The officer role shows there read-only. The Superadmin page shows only to the superadmin: it sets an org's officer role, adds an org for a Discord server the bot is in, removes an org, and shows the audit log of all orgs. It uses the `/api/superadmin/` routes. When the bot is not available, those routes return 503 and the page says so.

Each org sets its logo, accent color and website on the Settings page. The sidebar links to the website. The accent color sets the `--accent` CSS variable. Only primary buttons and the org initial use it. `--accent-fg` is black or white, for contrast. With no branding, the dashboard is gray and shows the first letter of the org name.

The dashboard uses the same type and colors as `site/`: Geist, Geist Mono and the gray tokens of the fumadocs-ui theme. The tokens are in `dashboard/src/index.css`. Light and dark follow the system; the switch at the bottom of the sidebar sets one. Transitions last 150 to 200 ms. If the system asks for reduced motion, the dashboard does not animate.

The sign-in page, the sign-in return and the org list use `AuthFrame`. It shows the Platform mark, the help links (Docs, GitHub, What is this?) and the org marks. Set `VITE_SITE_URL` to the URL of the `site/` deployment, and the Docs and What is this? links go to that site. Without it, they go to the docs and README on GitHub.

A resolved notification stays hidden while its problem has the same message. When the message changes, it is open again. The resolved ids are in the org config key `dashboard.resolved`.

The org marks (`OrgMarks` in `src/components/built-by.tsx`) show the orgs that build Platform as a row of round logos, one over the next. They show on the sign-in pages and at the bottom of the sidebar. To add an org:

1. Put a square SVG logo with a transparent background in `dashboard/public/orgs/` and in `site/public/orgs/`.
2. Add one entry to `BUILT_BY` in `dashboard/src/lib/links.ts` and to `orgs` in `site/lib/orgs.ts`: the name, the short name, the website, the logo path and the fill of the disk. The fill is fixed, so the logo looks the same on light and dark pages.

To check that long lists stay fast, run `npm run perf` in `dashboard/`. It answers the API from `largeFixtures()` in `scripts/fixtures.mjs` (2,000 knowledge sources, 1,500 members, 600 orders, 1,000 audit log entries) and prints the time of each step and its long tasks.

The landing page shows dashboard screenshots from `site/public/screenshots/`. After a UI change, run `npm run screenshots` in `dashboard/`. The script builds the dashboard, serves it with `vite preview` and answers each API call from `scripts/fixtures.mjs`, a fictional org. It needs Playwright with Chromium. If the Chromium version does not match Playwright, set `PLAYWRIGHT_CHROMIUM` to the browser binary.

The hero of the landing page plays a demo video from `site/public/demo/`: `platform-demo.mp4`, `platform-demo.webm` and `poster.webp`. After a UI change, run `npm run demo-video` in `dashboard/`. The script builds the dashboard and uses the same fixtures. It clicks and types through each page with Playwright and takes a screenshot each time the page changes. Then it draws each frame (the window, the camera zoom, the pointer and the captions) and encodes the files with ffmpeg. It needs Playwright with Chromium and `ffmpeg` with libx264, libvpx-vp9 and libwebp. A run takes about 15 minutes. To change the story or the captions, edit `story()` in `scripts/demo-video.mjs`. `DEMO_FPS` sets the frame rate, and `DEMO_CRF` and `DEMO_VP9_CRF` set the quality of the MP4 and WebM files.

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

### Code layout

`dashboard/src/pages/registry.tsx` lists every org page: its path, sidebar label, icon, sidebar section, optional module and page component. `src/app.tsx` makes the routes from this list, and `src/components/shell.tsx` makes the sidebar from it. A small page is one file in `src/pages/`. A large page is a folder, such as `src/pages/knowledge/`: `index.tsx` exports the page, and each other file holds one part. `shared.tsx` in a page folder holds the parts that two or more files of that page use.

These files hold the parts that two or more pages use. Use them on a new page. Do not style a one-off control.

| File | Holds |
| --- | --- |
| `src/components/ui/` (import from `components/ui`) | `PageHeader`, `Card`, `CardHeader`, `Row`, `Stat`, `StatGrid`, `Table`, `Th`, `Td`, `Tr`, `Button`, `DeleteButton`, `Input`, `SearchInput`, `Select`, `Textarea`, `Field`, `Switch`, `CheckOption`, `Badge`, `Dot`, `Mono`, `Code`, `EmptyState`, the loading skeletons, `ErrorNote`, `OkNote`, `Notice`, `Dialog`, `FormActions`, and `useShowMore` with `ShowMore` for long lists |
| `src/components/tabs.tsx` | `TabBar` and `useTabParam`: tabs that keep the open tab in `?tab=` |
| `src/components/tooltip.tsx` | `Tooltip`: a label on hover and keyboard focus, with optional keys. `Kbd` |
| `src/components/module-gate.tsx` | `ModuleGate` and `useModuleOn` |
| `src/components/activity-list.tsx` | The list of audit log entries |
| `src/lib/api.ts` | `api` and `send`, which call the API with the officer token |
| `src/lib/queries.ts` | Queries that two or more pages use, such as `useOverview` and `useModules` |
| `src/lib/format.ts` | Times, numbers, bytes and status tones |
| `src/lib/org.ts` | `useCurrentOrg`: the org in the URL |
| `src/lib/types/` | The shapes of the API responses, one file for each domain. `index.ts` exports all of them |

Put a part in `src/components/` or `src/lib/` only when two or more pages use it.

### Add a dashboard page

1. Write the page in `dashboard/src/pages/`. For a large page, make a folder with an `index.tsx` that exports the page.
2. Add one entry to `PAGES` in `src/pages/registry.tsx`. The order of `PAGES` is the order in the sidebar.
3. Add the types of the API responses to the domain file in `src/lib/types/`. If you add a file, export it from `src/lib/types/index.ts`.
4. Add a response for each API path the page reads to `dashboard/scripts/fixtures.mjs`.
5. Add a row for the page to the page table in this file.
6. Run `npm test` and `npm run build`.

These fields of a registry entry control who sees the page:

- `module`: the sidebar hides the page when the API says that this module is off for the org.
- `gate`: with `module`, the page shows a note with a link to Settings, Modules while the module is off. Without `gate`, the page opens and its API calls return 404.
- `superadmin`: only the superadmin sees the page in the sidebar. The page must also check `useSuperadmin()`.

An old path that opens another page goes in `REDIRECTS` in the same file.

## Member store

The member store is two open pages of `dashboard/`, outside the officer pages:

- `/store/<org>` shows the products in stock. A signed-in member also sees a cart, their points and their orders, and can place an order.
- `/store/<org>/login` signs a member in with `POST /api/points/<org>/member_login`.

These pages use the API session cookie, not the officer token. The order routes (`/api/storefront/<org>/members/...`) need a Discord session on the API. The browser sends the cookie only when the dashboard and the API are on the same site.

The older `web/` app is removed. Its pages are in the dashboard: member details are on Points (Add member, and Edit details in a member's history), and the store, calendar, compute and superadmin pages have dashboard pages. Its Jeopardy and bot pages called paths that the API does not have, so they are not in the dashboard.
