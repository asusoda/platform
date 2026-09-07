# 8. Frontend (the React admin app)

Lives in `web/`. It is a **Create React App** project (`react-scripts` 5.0.1) on **React 19**, using
**pnpm**. It is a pure client-side SPA: there is no server-side rendering and no backend code in
this folder. The production container just serves the built `build/` folder with `serve`.

## Stack

| Library | Used for |
|---------|----------|
| `react-router-dom` v6 | Routing |
| `axios` | All HTTP |
| `tailwindcss` v3 + `@mui/material` | Styling. **Both** are in use — Tailwind utility classes for most layout, MUI components in places. |
| `@tabler/icons-react`, `react-icons` | Icons |
| `motion` | Animation |
| `ogl` | WebGL, used only by the decorative `Orb` component |
| `react-toastify` | Toasts (`<ToastContainer />` sits at the app root) |
| `react-dropzone` | CSV and image uploads |

## Running it

```bash
# via containers (recommended, matches production)
make dev            # web on :5000

# or standalone
cd web && pnpm install && pnpm start    # PORT is pinned to 5000 in package.json
```

`REACT_APP_API_URL` is read at **build time** — it is a Docker build arg in `Dockerfile.web` and
compiled into the bundle. Changing it requires a rebuild, not a restart. Default when unset:
`https://api.thesoda.io` (`web/src/config.js`).

## Routing — `web/src/App.js`

The tree is `ErrorBoundary → BrowserRouter → AuthProvider → Routes`.

### Public

| Path | Page |
|------|------|
| `/`, `/login` | `LoginPage` — a single "Login with Discord" button that sends you to `{API}/api/auth/login` |
| `/auth` | `TokenRetrival` — reads `access_token` / `refresh_token` out of the URL query string into `localStorage`, fetches the user and orgs, then redirects |
| `/500` | `ServerError` |
| `/store/:orgPrefix` | `MemberStorePage` — public storefront browsing |
| `/store/:orgPrefix/login` | `MemberLoginPage` |
| `/metrics` | `MetricsPage` |

### Protected (`<PrivateRoute>`)

| Path | Page |
|------|------|
| `/select-organization` | `OrganizationSelector` — the landing page after login |
| `/superadmin` | `SuperAdmin` |
| `/:orgPrefix/dashboard` | `HomePage` |
| `/:orgPrefix/users` | `UserPage` |
| `/:orgPrefix/leaderboard` | `LeaderBoard` |
| `/:orgPrefix/addpoints` | `AddPoints` |
| `/:orgPrefix/calendar` | `Calendar` |
| `/:orgPrefix/storefront/dashboard` | `StorefrontDashboard` |
| `/:orgPrefix/storefront/products` | `StorefrontListPage` |
| `/:orgPrefix/add-storefront-product` | `AddStorefrontProductPage` |
| `/:orgPrefix/transactions` | `TransactionsPage` |
| `/:orgPrefix/panel` | `BotControlPanel` |
| `/:orgPrefix/gamepanel` | `GamePanel` |
| `/:orgPrefix/activegame` | `ActiveGame` |
| `/:orgPrefix/jeopardy` | `Jeopardy` |

### Legacy redirects

`/panel`, `/addpoints`, `/gamepanel`, `/activegame`, `/jeopardy`, `/home`, `/users`, `/leaderboard`
all `Navigate` to `/select-organization`. They exist because the app used to be single-org.

## Auth on the client — `web/src/components/auth/AuthContext.js`

`AuthProvider` is the single source of truth. It exposes:

```js
{ token, refreshToken, user, currentOrg, organizations, loading, isSuperAdmin,
  login, logout, selectOrganization, getApiClient, makeAuthenticatedRequest,
  refreshAccessToken, validateToken, /* plus raw setters */ }
```

State is hydrated from `localStorage` on mount: `accessToken`, `refreshToken`, `user`, `currentOrg`.

On mount (and whenever `token` changes) it runs:

```
validateToken()                    GET  /api/auth/validToken
  └─ invalid? refreshAccessToken() POST /api/auth/refresh
       └─ failed? logout()
getUserInfo()                      GET  /api/auth/name
fetchOrganizations()               GET  /api/organizations/
checkSuperAdminStatus()            GET  /api/superadmin/check
```

`logout()` POSTs `/api/auth/logout`, then clears all four `localStorage` keys and navigates to
`/login`.

### Two axios setups (both exist)

1. **`web/src/components/utils/axios.js`** — a module-level `apiClient` singleton. Its request
   interceptor pulls the token straight out of `localStorage` and adds `X-Organization-ID` /
   `X-Organization-Prefix` from the stored `currentOrg`. Its response interceptor retries once on
   **403** after refreshing. Most pages import this.
2. **`AuthContext.getApiClient()`** — creates a fresh axios instance per call, using the token from
   React state. Same 403-refresh behaviour. `SuperAdmin` and `Calendar` use this one.

They do the same job. Prefer `apiClient` for new code unless you specifically need React state.

Remember the contract from [Authentication](./04-authentication.md): **403 means refresh, 401 means
log out.** Both interceptors are written against that.

### `PrivateRoute` — `web/src/components/auth/PrivateRoute.js`

```
loading?                       → <ThemedLoading />
no token?                      → redirect /
route has :orgPrefix?
   not in the user's orgs?     → redirect /select-organization
   currentOrg doesn't match?   → redirect /select-organization
no :orgPrefix and orgs exist and no currentOrg,
   and path isn't one of /select-organization, /auth, /500, /superadmin
                               → redirect /select-organization
otherwise                      → render children
```

It logs its decision to the console on every render. Noisy, but useful when debugging redirect loops
— which is the most common frontend problem in this app.

## Organization-aware navigation — `web/src/hooks/useOrgNavigation.js`

Do not hardcode paths. Use this hook:

```js
const { goToDashboard, goToUsers, goToLeaderboard, navigateToOrg, getOrgPath } = useOrgNavigation();
```

`getOrgPath("users")` returns `/{currentOrg.prefix}/users`, or the bare path if no org is selected.

## Component map

| Area | Files |
|------|-------|
| Layout / chrome | `NavBar`, `SideBar`, `DashBoard`, `OrganizationSwitcher`, `shared/OrganizationNavbar.jsx` |
| Auth | `auth/AuthContext.js`, `auth/PrivateRoute.js`, `LoginButton` |
| Storefront | `editProductModal`, `UploadFileCard`, `ui/file-upload.jsx`, `constants/productCategories.js` |
| Jeopardy | `GameBoard`, `GameCard`, `GameTable` (empty file), `QuestionPanel`, `RevealQuestion`, `AwardPanel`, `SetupButton` |
| Points | `points/api.js` |
| UI primitives | `ui/InlineEdit`, `ui/Orb.jsx`, `ui/StarBorder.jsx`, `ui/ThemedLoading.jsx`, `ui/navbar-menu.jsx`, `ui/OrganizationCard.js`, `ToggleSwitch` |
| Robustness | `ErrorBoundary`, `utils/errorSuppression.js`, `utils/resizeObserverFix.js` |

`errorSuppression.js` and `resizeObserverFix.js` exist to swallow the benign
`ResizeObserver loop completed with undelivered notifications` error that CRA's dev overlay turns
into a full-screen crash. They are workarounds, not features.

## Pages that do not work

Several Jeopardy/bot pages call API paths that **do not exist on the backend**. The backend serves
Jeopardy under `/api/bot/*`; these call something else entirely:

| File | Calls | Backend actually serves |
|------|-------|------------------------|
| `pages/ActiveGame.js` | `/games/active` | `/api/bot/getactivegame` |
| `pages/GamePanel.js` | `/games/list` | `/api/bot/getavailablegames` |
| `pages/Jeopardy.js` | `/jeopardy/games` | `/api/bot/getavailablegames` |
| `pages/BotControlPanel.js` | `/bot/status` | *(commented out in `modules/bot/api.py`)* |
| `components/AwardPanel.js` | `/api/awardpoints` | `/api/bot/awardpoints` |
| `components/SetupButton.js` | `/api/createchannels`, `/api/startactivegame` | `/api/bot/startactivegame` (no `createchannels` route) |
| `components/GameBoard.js` | `/api/getgamequestions` | *(no such route)* |

These pages will render and then fail on their first request. If you are asked to "fix Jeopardy",
this mismatch is where to start. Also noted in [Gotchas](./10-gotchas-and-known-issues.md).

## Tests

`web/src/App.test.js` is the untouched CRA boilerplate ("learn react" link test), which does not
match this app. There is effectively no frontend test coverage.
