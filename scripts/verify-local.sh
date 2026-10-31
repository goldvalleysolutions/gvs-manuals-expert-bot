#!/usr/bin/env bash
# verify-local.sh: run this bot repo's checks locally and print a Markdown "Local verification" block.
# Usage: scripts/verify-local.sh [--allow-missing] [-h]
# Env:   GVS_E2E_REQUIRED=1   the Playwright e2e suite must run: missing pytest/playwright is a FAIL
#                             (even with --allow-missing) and the suite fails instead of skipping
#        GVS_CORE_DIR=<path>  gvs-core-bot checkout at the e2e CORE_SHA (requirements installed);
#                             unset: tests/e2e clones it into .e2e/core (needs GitHub access)
#        PYTHON=python3       interpreter with core + tests/e2e requirements installed
#        CORE_IMAGE=<ref>     base image for the docker build (default: the Dockerfile's ARG)
#        VERIFY_SKIP="semgrep"  checks to skip (first word or full label); reason: VERIFY_SKIP_REASON
# Rows:  PASS / FAIL / SKIP. Docker rows SKIP under --allow-missing when Docker is absent or down.
# Exit:  non-zero if any check FAILs, a required tool is MISSING (without --allow-missing), or the tree is dirty.
# Same row/flag conventions as gvs-factory scripts/verify-local.sh. Kept identical across the bot repos.
set -u

ALLOW_MISSING=0
for arg in "$@"; do
  case "$arg" in
    --allow-missing) ALLOW_MISSING=1 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "not a git repository" >&2; exit 2; }
cd "$ROOT" || exit 2
PY=${PYTHON:-python3}
read -r -a SKIPS <<<"${VERIFY_SKIP:-}"
SKIP_REASON=${VERIFY_SKIP_REASON:-not part of this run}
LOG_DIR=$(mktemp -d "${TMPDIR:-/tmp}/verify-local.XXXXXX")
ROWS=()
FAILED=0
SLUG=$(sed -n 's/^slug:[[:space:]]*//p' bot/bot.yaml | head -1)
E2E_REQUIRED=${GVS_E2E_REQUIRED:-0}

have() { command -v "$1" >/dev/null 2>&1; }
add_row() { ROWS+=("| \`$1\` | $2 | $3 |"); }
log_name() { printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '_' | cut -c1-60; printf -- '-%08x' "$(printf '%s' "$1" | cksum | awk '{print $1}')"; }
skip() { add_row "$1" "SKIP ($2)" "0s"; }
run() {
  local label=$1; shift
  local k start rc logf
  for k in "${SKIPS[@]}"; do
    if [ "$k" = "${label%% *}" ] || [ "$k" = "$label" ]; then skip "$label" "$SKIP_REASON"; return 0; fi
  done
  logf="$LOG_DIR/$(log_name "$label").log"
  start=$(date +%s)
  "$@" >"$logf" 2>&1
  rc=$?
  if [ $rc -eq 0 ]; then add_row "$label" PASS "$(( $(date +%s) - start ))s"
  else add_row "$label" "FAIL (exit $rc, log $logf)" "$(( $(date +%s) - start ))s"; FAILED=1; fi
  return $rc
}
# missing <label> <why> [required]: SKIP under --allow-missing unless required, else FAIL
missing() {
  if [ $ALLOW_MISSING -eq 1 ] && [ "${3:-}" != required ]; then add_row "$1" "SKIP (MISSING: $2, allowed)" "0s"
  else add_row "$1" "FAIL (MISSING: $2)" "0s"; FAILED=1; fi
}
py_has() { "$PY" -c "import $1" >/dev/null 2>&1; }

if [ -n "$(git status --porcelain)" ]; then TREE="DIRTY (uncommitted changes; results do not match the head SHA)"; DIRTY=1; else TREE="clean"; DIRTY=0; fi

# Core checkout for bot.yaml lint (same one the e2e suite uses)
CORE_DIR=${GVS_CORE_DIR:-$ROOT/.e2e/core}

# 1. Lint
if have ruff; then run "ruff check bot scripts tests" ruff check bot scripts tests
else missing "ruff check" "ruff not installed"; fi
run "python -m compileall bot scripts tests" "$PY" -m compileall -q bot scripts tests
if have shellcheck; then run "shellcheck scripts/*.sh" bash -c 'shellcheck scripts/*.sh'
else missing "shellcheck scripts/*.sh" "shellcheck not installed"; fi
if [ -f "$CORE_DIR/core/config/lint.py" ]; then
  run "core.config.lint bot (bot.yaml schema + core pin)" bash -c "cd '$CORE_DIR' && '$PY' -m core.config.lint '$ROOT/bot'"
else missing "core.config.lint bot" "no core checkout (set GVS_CORE_DIR)"; fi

# 2. Unit tests (anything under tests/ outside tests/e2e)
if ! py_has pytest; then missing "pytest (unit)" "pytest not installed"
elif find tests -name 'test_*.py' -not -path 'tests/e2e/*' | grep -q .; then
  run "pytest -q --ignore=tests/e2e (unit)" "$PY" -m pytest -q -p no:cacheprovider --ignore=tests/e2e tests
else skip "pytest -q --ignore=tests/e2e (unit)" "no unit tests in this repo; behavior is covered by tests/e2e"; fi

# 3. Playwright e2e, stub LLM, desktop + mobile
E2E_LABEL="pytest tests/e2e (Playwright, stub LLM, desktop + mobile)"
REQ=""; [ "$E2E_REQUIRED" = 1 ] && REQ=required
if ! py_has pytest || ! py_has playwright; then
  missing "$E2E_LABEL" "pytest/playwright not installed for $PY" $REQ
else
  if run "$E2E_LABEL" env GVS_E2E_REQUIRED="$E2E_REQUIRED" "$PY" -m pytest tests/e2e -q -p no:cacheprovider -rs; then
    last=$(grep -E '[0-9]+ (passed|failed|skipped)' "$LOG_DIR/$(log_name "$E2E_LABEL").log" | tail -1 | tr -d '=' | sed 's/^ *//;s/ in [0-9.]*s.*$//')
    ROWS[-1]=${ROWS[-1]/| PASS |/| PASS ($last) |}
  fi
fi

# 4. Docker image build (+ the image walkthrough)
if have docker && docker info >/dev/null 2>&1; then
  BUILD=(docker build -q -f bot/Dockerfile -t "${SLUG}-bot:verify")
  [ -n "${CORE_IMAGE:-}" ] && BUILD+=(--build-arg "CORE_IMAGE=$CORE_IMAGE")
  if run "docker build -f bot/Dockerfile -t ${SLUG}-bot:verify ." "${BUILD[@]}" .; then
    run "scripts/${SLUG}-steps.sh ${SLUG}-bot:verify" "scripts/${SLUG}-steps.sh" "${SLUG}-bot:verify"
  else skip "scripts/${SLUG}-steps.sh" "image did not build"; fi
else
  why="docker not installed"; have docker && why="docker daemon not reachable"
  missing "docker build -f bot/Dockerfile" "$why"
  missing "scripts/${SLUG}-steps.sh (image walkthrough)" "$why"
fi

# 5. Repo-wide security scans
if have gitleaks; then run "gitleaks dir ." gitleaks dir . --redact --no-banner; else missing "gitleaks" "not installed"; fi
if have semgrep; then run "semgrep scan --config p/ci --error" semgrep scan --config p/ci --error --quiet --metrics=off --disable-version-check
else missing "semgrep" "not installed"; fi

[ $DIRTY -eq 1 ] && FAILED=1

cat <<OUT
## Local verification

- Repo: $(basename "$(git config --get remote.origin.url 2>/dev/null || echo "$ROOT")" .git)
- Branch: $(git rev-parse --abbrev-ref HEAD)
- Head SHA: $(git rev-parse HEAD)
- Tree: $TREE
- Time: $(TZ=America/New_York date '+%Y-%m-%d %H:%M') America/New_York
- Flags: $([ $ALLOW_MISSING -eq 1 ] && echo --allow-missing || echo none); GVS_E2E_REQUIRED=$E2E_REQUIRED

| Command | Result | Duration |
|---|---|---|
OUT
printf '%s\n' "${ROWS[@]}"
echo
if [ $FAILED -eq 0 ]; then echo "Overall: PASS"; else echo "Overall: FAIL"; fi
exit $FAILED
