#!/usr/bin/env bash
# Manuals Expert walkthrough against a built image. Stub LLM, fake SMTP, MCP.
# No REST API: the driver uses web chat, the admin forms (with CSRF) and the MCP client.
# It runs inside the image so core.auth.token / mcp / httpx2 / cryptography come from core.
# The Playwright suite in tests/e2e is the required pre-merge check; this checks the image.
# Usage: scripts/manuals-expert-steps.sh <image> [host-port]
set -euo pipefail

image="${1:?usage: scripts/manuals-expert-steps.sh <image> [port]}"
port="${2:-18085}"
name="manuals-expert-steps-$(echo "$image" | tr -c 'a-zA-Z0-9' '-')$$"
vol="${name}-data"
here="$(cd "$(dirname "$0")/.." && pwd)"
ctl="$(mktemp -d "${TMPDIR:-/tmp}/manuals-expert-steps.XXXXXX")"
smtp_pid=""

cleanup() {
  if [[ -n "${smtp_pid}" ]]; then kill "${smtp_pid}" >/dev/null 2>&1 || true; fi
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker volume rm "$vol" >/dev/null 2>&1 || true
  rm -rf "$ctl"
}
trap cleanup EXIT

fail() { echo "FAIL $*" >&2; exit 1; }

in_image() {
  docker run --rm --user "$(id -u):$(id -g)" -e PYTHONPATH=/app \
    -v "$here/scripts:/steps:ro" -v "$ctl:/ctl" "$@"
}

python3 "$here/scripts/fakesmtp.py" > "$ctl/smtp.port" &
smtp_pid=$!
for _ in $(seq 1 50); do [[ -s "$ctl/smtp.port" ]] && break; sleep 0.1; done
smtp_port="$(tr -d '[:space:]' < "$ctl/smtp.port")"
[[ -n "$smtp_port" ]] || fail "fakesmtp printed no port"

in_image "$image" python -c \
  "import sys; sys.path.insert(0, '/steps'); from pathlib import Path; from steps_web import write_root_key; write_root_key(Path('/ctl'))"
[[ -s "$ctl/gvs_root.pub" ]] || fail "runtime root key not written"

docker run -d --name "$name" --add-host=host.docker.internal:host-gateway \
  -p "127.0.0.1:${port}:8080" -v "${vol}:/data" "$image" >/dev/null

start=$(date +%s)
until curl -fsS "http://127.0.0.1:${port}/health" >/dev/null; do
  if (( $(date +%s) - start >= 60 )); then
    echo "FAIL /health not up" >&2; docker logs "$name" >&2 || true; exit 1
  fi
  sleep 1
done

docker cp "$ctl/gvs_root.pub" "$name:/tmp/gvs_root.pub"
docker exec -u 0 "$name" cp /tmp/gvs_root.pub /app/keys/gvs_root.pub
bot_id="$(docker exec "$name" python -c "import sqlite3; c=sqlite3.connect('/data/bot.db'); print(c.execute(\"select value from settings where key='bot_id'\").fetchone()[0])")"
[[ -n "$bot_id" ]] || fail "no bot_id in /data/bot.db"

in_image --network "container:${name}" "$image" \
  python /steps/manuals_expert_steps_http.py http://127.0.0.1:8080 host.docker.internal "$smtp_port" /ctl "$bot_id"
