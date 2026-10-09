#!/usr/bin/env bash
# Runs Hermes Agent (Nous Research) on the platform pod as the user hermes, with this platform's MCP tools.
# start.sh calls it when HERMES_ENV_DISCORD_BOT_TOKEN is set. Run it from the repository root as root.
# Hermes gets only the HERMES_ENV_* variables, without the prefix, so it cannot read the platform's settings.
# Its files are in /workspace/hermes/home, which it owns. /workspace/data and the platform checkout are closed to it.
set -euo pipefail

DIR=/workspace/hermes
VERSION="${HERMES_VERSION:-v2026.9.24}"
HOME_DIR="$DIR/home"
mkdir -p "$DIR"

id hermes >/dev/null 2>&1 || useradd --system --home-dir "$HOME_DIR" --shell /usr/sbin/nologin hermes
mkdir -p "$HOME_DIR"
chown -R hermes:hermes "$HOME_DIR"
chmod 700 "$HOME_DIR" /workspace/data
chmod 750 /workspace/platform

# Hermes supports install from its source tree only. A new HERMES_VERSION replaces the checkout.
if [ "$(cat "$DIR/version" 2>/dev/null)" != "$VERSION" ]; then
  rm -rf "$DIR/src" "$DIR/venv"
  git -c advice.detachedHead=false clone -q --depth 1 --branch "$VERSION" https://github.com/NousResearch/hermes-agent.git "$DIR/src"
  (cd "$DIR/src" && UV_PROJECT_ENVIRONMENT="$DIR/venv" uv sync -q --frozen --no-dev --extra messaging --extra mcp)
  echo "$VERSION" > "$DIR/version"
fi
chmod -R o+rX "$DIR/src" "$DIR/venv"
chmod o+x "$DIR"

env_args=(HOME="$HOME_DIR" HERMES_HOME="$HOME_DIR" PATH="$DIR/venv/bin:/usr/local/bin:/usr/bin:/bin" LANG=C.UTF-8)
while IFS='=' read -r name _; do
  case "$name" in
    HERMES_ENV_*) env_args+=("${name#HERMES_ENV_}=${!name}") ;;
  esac
done < <(env)
hermes_run() {
  env -i "${env_args[@]}" setpriv --reuid=hermes --regid=hermes --init-groups "$DIR/venv/bin/hermes" "$@"
}

# The model and the platform MCP server go into config.yaml on each start. Other settings in it are kept.
[ -z "${HERMES_PROVIDER:-}" ] || hermes_run config set model.provider "$HERMES_PROVIDER" >/dev/null
[ -z "${HERMES_MODEL:-}" ] || hermes_run config set model.default "$HERMES_MODEL" >/dev/null
[ -z "${HERMES_BASE_URL:-}" ] || hermes_run config set model.base_url "$HERMES_BASE_URL" >/dev/null
if [ -n "${HERMES_PLATFORM_TOKEN:-}" ]; then
  env_args+=(PLATFORM_MCP_URL="${HERMES_PLATFORM_MCP_URL:-http://127.0.0.1:${MCP_PORT:-8001}/mcp}")
  env_args+=(PLATFORM_TOKEN="$HERMES_PLATFORM_TOKEN")
  hermes_run config set mcp_servers.platform.url '${PLATFORM_MCP_URL}' >/dev/null
  hermes_run config set mcp_servers.platform.headers.Authorization 'Bearer ${PLATFORM_TOKEN}' >/dev/null
else
  echo "[hermes] HERMES_PLATFORM_TOKEN is not set; Hermes runs without platform tools" >&2
fi

while true; do
  hermes_run gateway run || true
  echo "[hermes] gateway stopped; restart in 10 s" >&2
  sleep 10
done
