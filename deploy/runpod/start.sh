#!/usr/bin/env bash
# Runs the platform on one RunPod pod: API on 8000, dashboard on 5000, MCP server on 8001, bot when BOT_TOKEN is set.
# RUN_BOT=false skips the bot, for a BOT_TOKEN that another bot process already uses.
# It also runs the shared browser and SearXNG on 127.0.0.1. RUN_BROWSER=false and RUN_SEARCH=false turn them off.
# The pod clones PLATFORM_BRANCH into /workspace on each start, so a restart deploys the branch head.
# State (SQLite database, generated keys) lives in /workspace/data on the pod's volume.
set -euo pipefail

REPO="${PLATFORM_REPO:-https://github.com/theaisocietyasu/bedrock.git}"
BRANCH="${PLATFORM_BRANCH:-main}"
ROOT=/workspace/platform
DATA=/workspace/data
mkdir -p "$DATA"

if [ -d "$ROOT/.git" ]; then
  git -C "$ROOT" fetch --depth 1 origin "$BRANCH"
  git -C "$ROOT" checkout -q -B "$BRANCH" FETCH_HEAD
else
  git clone --depth 1 --branch "$BRANCH" "$REPO" "$ROOT"
fi
cd "$ROOT"

# Keys generated once and kept on the volume, so sessions and encrypted secrets survive restarts
if [ ! -f "$DATA/keys.env" ]; then
  python3 -c 'import base64, os, secrets; print(f"SECRET_KEY={secrets.token_urlsafe(48)}"); print("SECRETS_KEY=" + base64.urlsafe_b64encode(os.urandom(32)).decode())' > "$DATA/keys.env"
  chmod 600 "$DATA/keys.env"
fi
set -a
# shellcheck disable=SC1091
. "$DATA/keys.env"
set +a

API_URL="${API_URL:-https://${RUNPOD_POD_ID}-8000.proxy.runpod.net}"
WEB_URL="${WEB_URL:-https://${RUNPOD_POD_ID}-5000.proxy.runpod.net}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$DATA/user.db}"
export REDIRECT_URI="${REDIRECT_URI:-$API_URL/api/auth/callback}"
export ACCOUNTS_BASE_URL="${ACCOUNTS_BASE_URL:-$API_URL}"
# The MCP server has its own proxy host on the pod, so OAuth cannot use <API_URL>/mcp
export MCP_PUBLIC_URL="${MCP_PUBLIC_URL:-https://${RUNPOD_POD_ID}-8001.proxy.runpod.net/mcp}"
export CLIENT_URL="${CLIENT_URL:-$WEB_URL}"
export DASHBOARD_URL="${DASHBOARD_URL:-$WEB_URL}"
export CORS_EXTRA_ORIGINS="${CORS_EXTRA_ORIGINS:-$WEB_URL}"
export IS_PROD=true FLASK_ENV=production FLASK_DEBUG=0 RUN_BOT_IN_API=false LOG_FORMAT=json

python3 -m pip install -q uv
if [ "${RUN_BROWSER:-true}" != "false" ]; then
  uv sync --frozen --no-dev --extra browser
else
  uv sync --frozen --no-dev
fi
(cd dashboard && npm ci --no-audit --no-fund && VITE_API_URL="$API_URL" npm run build)
uv run alembic upgrade head
# Logs the Discord app of BOT_TOKEN and any setting that is missing. A failure does not stop the start.
uv run flask --app main config check || true

# First boot: create the org named by ORG_PREFIX, ORG_NAME and ORG_GUILD_ID if it does not exist yet
if [ -n "${ORG_PREFIX:-}" ] && [ -n "${ORG_GUILD_ID:-}" ]; then
  if ! uv run flask --app main org list | cut -f2 | grep -qx "$ORG_PREFIX"; then
    uv run flask --app main org create --name "${ORG_NAME:-$ORG_PREFIX}" --prefix "$ORG_PREFIX" \
      --guild-id "$ORG_GUILD_ID" ${ORG_OFFICER_ROLE_ID:+--officer-role-id "$ORG_OFFICER_ROLE_ID"} \
      ${ORG_MODULES_OFF:+--off "$ORG_MODULES_OFF"}
  fi
fi

# The shared browser, a Playwright server for pages that need JavaScript and the ASU sign-in.
# Chromium is kept on the volume. A failure does not stop the start; pages are then read without it.
start_browser() {
  export PLAYWRIGHT_BROWSERS_PATH="$DATA/ms-playwright"
  uv run playwright install --with-deps chromium || return 1
  uv run playwright run-server --port 3000 --host 127.0.0.1 &
  export BROWSER_URL="ws://127.0.0.1:3000/"
}
if [ "${RUN_BROWSER:-true}" != "false" ] && [ -z "${BROWSER_URL:-}" ]; then
  start_browser || echo "the browser did not start; pages are read without JavaScript" >&2
fi

# SearXNG, the deployment default for web search, at the commit of the searxng image in docker-compose.yml.
# The code and its virtualenv are kept on the volume. A failure does not stop the start; web search then answers 503.
SEARXNG_COMMIT=d4f00d15d
start_searxng() {
  local dir="$DATA/searxng"
  if [ ! -f "$dir/.ready-$SEARXNG_COMMIT" ]; then
    rm -rf "$dir"
    git clone -q --filter=blob:none --no-checkout https://github.com/searxng/searxng.git "$dir" || return 1
    git -C "$dir" checkout -q "$SEARXNG_COMMIT" || return 1
    python3 -m venv "$dir/venv" || return 1
    "$dir/venv/bin/pip" install -q -r "$dir/requirements.txt" || return 1
    touch "$dir/.ready-$SEARXNG_COMMIT"
  fi
  if [ ! -f "$DATA/searxng.env" ]; then
    python3 -c 'import secrets; print(f"SEARXNG_SECRET={secrets.token_hex(32)}")' > "$DATA/searxng.env"
    chmod 600 "$DATA/searxng.env"
  fi
  (
    set -a
    # shellcheck disable=SC1091
    . "$DATA/searxng.env"
    set +a
    cd "$dir"
    SEARXNG_SETTINGS_PATH="$ROOT/deploy/searxng/settings.yml" SEARXNG_BIND_ADDRESS=127.0.0.1 SEARXNG_PORT=8888 \
      exec "$dir/venv/bin/python" -m searx.webapp
  ) &
  export SEARXNG_URL="http://127.0.0.1:8888"
}
if [ "${RUN_SEARCH:-true}" != "false" ] && [ -z "${SEARXNG_URL:-}" ]; then
  start_searxng || echo "SearXNG did not start; web search answers 503" >&2
fi

npx --yes serve@14 -s dashboard/dist -l 5000 &
uv run python mcp_main.py &
if [ -n "${BOT_TOKEN:-}" ] && [ "${RUN_BOT:-true}" != "false" ]; then
  uv run python bot_main.py &
fi
exec uv run gunicorn --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:8000 main:app
