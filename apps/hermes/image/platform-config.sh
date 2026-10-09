#!/command/with-contenv sh
# shellcheck shell=sh
# Writes the model and the Platform MCP server into /opt/data/config.yaml on every start.
# Runs after the image's own setup has seeded config.yaml. Other settings in the file are kept.
# The MCP url and token stay as ${...} placeholders that Hermes fills from the environment.
set -e

hermes_set() {
    s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set "$1" "$2" >/dev/null
}

if [ -n "${HERMES_PROVIDER:-}" ]; then
    hermes_set model.provider "$HERMES_PROVIDER"
fi
if [ -n "${HERMES_MODEL:-}" ]; then
    hermes_set model.default "$HERMES_MODEL"
fi
if [ -n "${PLATFORM_MCP_URL:-}" ] && [ -n "${PLATFORM_TOKEN:-}" ]; then
    hermes_set mcp_servers.platform.url '${PLATFORM_MCP_URL}'
    hermes_set mcp_servers.platform.headers.Authorization 'Bearer ${PLATFORM_TOKEN}'
    echo "[platform] Platform MCP server set to $PLATFORM_MCP_URL"
else
    echo "[platform] PLATFORM_MCP_URL or PLATFORM_TOKEN not set; Hermes runs without Platform tools"
fi
