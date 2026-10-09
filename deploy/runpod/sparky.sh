#!/usr/bin/env bash
# Runs Sparky (engine and Discord bot) on the platform pod, with this platform as its store.
# start.sh calls it when SPARKY_DISCORD__TOKEN and SPARKY_PLATFORM__TOKEN are set. Run it from the repository root.
# The binaries come from the public image SPARKY_IMAGE at SPARKY_TAG. The model is any OpenAI-compatible API at
# SPARKY_MODEL__BASE_URL: a hosted API, or llama-server on a GPU pod. See docs/operations.md.
set -euo pipefail

DIR=/workspace/sparky
IMAGE="${SPARKY_IMAGE:-ghcr.io/ashworks1706/sparkyai-rust}:${SPARKY_TAG:-main}"
mkdir -p "$DIR"
chmod 700 "$DIR"

uv run python -m deploy.runpod.image_files "$IMAGE" "$DIR/bin" engine discord sparky.toml

# The bot calls the engine with this token. Generated once and kept on the volume.
if [ ! -f "$DIR/keys.env" ]; then
  python3 -c 'import secrets; print(f"SPARKY_ENGINE__SERVICE_TOKEN={secrets.token_urlsafe(32)}")' > "$DIR/keys.env"
  chmod 600 "$DIR/keys.env"
fi
set -a
# shellcheck disable=SC1091
. "$DIR/keys.env"
set +a

export SPARKY_CONFIG_FILE="$DIR/bin/sparky.toml"
export SPARKY_APP__ENV="${SPARKY_APP__ENV:-production}"
export SPARKY_PLATFORM__ENABLED=true
export SPARKY_PLATFORM__URL="${SPARKY_PLATFORM__URL:-http://127.0.0.1:8000}"
export SPARKY_APP__HTTP_ADDR="${SPARKY_APP__HTTP_ADDR:-127.0.0.1:8080}"
export SPARKY_ENGINE__BASE_URL="http://${SPARKY_APP__HTTP_ADDR}"
# The pod cannot run containers, so run_sandbox stays off.
export SPARKY_SANDBOX__ENABLED=false
# The summary model is the chat model unless set apart.
for key in BASE_URL API_KEY NAME; do
  model="SPARKY_MODEL__$key" summary="SPARKY_SUMMARY__$key"
  if [ -n "${!model:-}" ] && [ -z "${!summary:-}" ]; then
    export "$summary=${!model}"
  fi
done
# Without SPARKY_EMBEDDING__BASE_URL the platform embeds each query with the Embeddings integration.
if [ -z "${SPARKY_EMBEDDING__BASE_URL:-}" ]; then
  export SPARKY_RETRIEVAL__DENSE=false
fi

# Restarts a process 10 seconds after it stops, for example while the API is still starting.
keep() {
  while true; do
    "$@" || true
    echo "[sparky] $1 stopped; restart in 10 s" >&2
    sleep 10
  done
}

cd "$DIR"
keep "$DIR/bin/engine" &
keep "$DIR/bin/discord" &
wait
