# knowledge.asu_signin

The ASU sign-in. An officer signs in to ASU once with a NetID, a password and Duo, on the ASU card of the Shared tab of Explore. Platform keeps only the browser cookies, as the org secret `asu_session`. Two live queries of [knowledge.asu](../asu/README.md) then read Sun Devil Central with it, like any other live query (`search` with a source, or `knowledge.query`):

| Query | Parameters | Reads |
| --- | --- | --- |
| `clubs` | keywords (required) | The Sun Devil Central club directory |
| `club_events` | keywords (required) | The Sun Devil Central events |

## Files

| File | Holds |
| --- | --- |
| `__init__.py` | `SUBMODULE` |
| `content.py` | Registers the sign-in as `asu` in `modules/knowledge/content/signins.py` |
| `browser.py` | The `Browser` interface and `Chromium`, which runs headless Chromium through Playwright |
| `sso.py` | The sign-in on a page: the ASU form, Duo and its code, the Sun Devil Central sign-in link, and the check for a sign-in page |
| `sundevil_central.py` | The club and event URLs and extractors |
| `service.py` | Sign-in attempts, the saved session, page loads with it, and the `asu.session_expired` event |

## Surface

- Switch: `knowledge.asu_signin`. The sign-in and the two queries need it and `knowledge.asu` on. Migration `c5e7a9b1d3f4` turned it on for each org that had saved a sign-in.
- Routes: `GET`, `POST` and `DELETE /api/dashboard/<org>/submodules/asu/signin` in `modules/dashboard/api.py`. Sign-out works with the switch off, so the saved session can go.
- Secret: `asu_session`. Event: `asu.session_expired`.

Playwright is an optional extra: `uv sync --extra browser`. The API image has it. With `BROWSER_URL` set, the sign-in uses the shared browser ([operations](../../../../docs/operations.md#run-the-shared-browser)). Its requests go through the guard of `core/browser.py`, which loads public addresses only and closes WebSockets. Without `BROWSER_URL`, run `uv run playwright install --with-deps chromium` on the machine. Without the package, the card says so and the two queries refuse. Their results are never added to knowledge. See [docs/integrations.md](../../../../docs/integrations.md#sign-in-to-asu).
