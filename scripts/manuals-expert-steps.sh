#!/usr/bin/env bash
# Manuals Expert walkthrough against a built manuals-expert-bot image.
# Stub LLM, MCP, tool + REST parity. Usage: scripts/manuals-expert-steps.sh <image> [host-port]
set -euo pipefail

image="${1:?usage: scripts/manuals-expert-steps.sh <image> [port]}"
port="${2:-18085}"
name="manuals-steps-$(echo "$image" | tr -c 'a-zA-Z0-9' '-')$$"
vol="${name}-data"
here="$(cd "$(dirname "$0")/.." && pwd)"
base="http://127.0.0.1:${port}"

cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker volume rm "$vol" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run -d --name "$name" \
  -p "127.0.0.1:${port}:8080" \
  -v "${vol}:/data" \
  "$image" >/dev/null

start=$(date +%s)
until curl -fsS "${base}/health" >/dev/null; do
  if (( $(date +%s) - start >= 60 )); then
    echo "FAIL /health not up" >&2
    docker logs "$name" >&2 || true
    exit 1
  fi
  sleep 1
done

docker run --rm --network container:"$name" \
  -v "$here/scripts:/steps:ro" \
  "$image" \
  python /steps/manuals_expert_steps_http.py http://127.0.0.1:8080

listed="$(docker exec "$name" ls /data/manuals-expert)"
echo "$listed"
echo "$listed" | grep -q "maple-espresso-e20.md" || {
  echo "FAIL expected maple-espresso-e20.md in /data/manuals-expert" >&2
  exit 1
}
