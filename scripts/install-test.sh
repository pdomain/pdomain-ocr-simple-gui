#!/usr/bin/env bash
# Start and follow a manual install test on GitHub Actions:
# .github/workflows/macos-install.yml or windows-install.yml.
#
# Usage:
#   scripts/install-test.sh <macos|windows> start [runner]   start a run on master and follow it
#   scripts/install-test.sh <macos|windows> watch [run-id]   follow a run; default: the newest one
#   scripts/install-test.sh <macos|windows> logs [run-id]    print the failed steps' logs
#
# macOS runners: macos-26 (default) or macos-15, both Apple Silicon.
# Windows runners: windows-2025 (default) or windows-2022, both x64.
# The workflow must already be on master, because GitHub only dispatches
# workflows that exist on the ref.
set -euo pipefail

case "${1:-}" in
  macos)
    readonly WORKFLOW="macos-install.yml" DEFAULT_RUNNER="macos-26" RECIPE="mac-test"
    ;;
  windows)
    readonly WORKFLOW="windows-install.yml" DEFAULT_RUNNER="windows-2025" RECIPE="win-test"
    ;;
  *)
    echo "Usage: $0 <macos|windows> start [runner] | watch [run-id] | logs [run-id]" >&2
    exit 2
    ;;
esac
shift

repo_slug() {
  local url
  url="$(git remote get-url origin)"
  url="${url#git@github.com:}"
  url="${url#https://github.com/}"
  printf '%s\n' "${url%.git}"
}

newest_run() {
  local run_id
  run_id="$(gh run list -R "$REPO" --workflow "$WORKFLOW" --limit 1 \
    --json databaseId -q '.[0].databaseId')"
  if [[ -z "$run_id" ]]; then
    echo "ERROR: $REPO has no $WORKFLOW runs yet. Start one with: just $RECIPE" >&2
    exit 1
  fi
  printf '%s\n' "$run_id"
}

watch_run() {
  local run_id="$1" status=0
  echo "Following run $run_id: https://github.com/$REPO/actions/runs/$run_id"
  gh run watch -R "$REPO" "$run_id" --exit-status --interval 30 || status=$?
  if [[ "$status" -ne 0 ]]; then
    echo ""
    echo "The run failed. Failed steps:"
    gh run view -R "$REPO" "$run_id" --log-failed | tail -n 80 || true
    echo ""
    echo "Full logs: just $RECIPE-logs $run_id"
  fi
  return "$status"
}

start_run() {
  local runner="$1" started run_id="" attempt
  started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  gh workflow run -R "$REPO" "$WORKFLOW" --ref master -f "runner=$runner"
  echo "Started $WORKFLOW on $runner. Waiting for GitHub to list the run..."
  for attempt in $(seq 1 20); do
    run_id="$(gh run list -R "$REPO" --workflow "$WORKFLOW" --event workflow_dispatch \
      --limit 5 --json databaseId,createdAt \
      -q "map(select(.createdAt >= \"$started\")) | .[0].databaseId // empty")"
    [[ -n "$run_id" ]] && break
    echo "  not listed yet (attempt $attempt of 20)"
    sleep 3
  done
  if [[ -z "$run_id" ]]; then
    echo "ERROR: GitHub did not list the new run within a minute." >&2
    echo "       Find it with: gh run list -R $REPO --workflow $WORKFLOW" >&2
    exit 1
  fi
  watch_run "$run_id"
}

REPO="$(repo_slug)"
readonly REPO

pick_run() {
  if [[ -n "${1:-}" ]]; then
    printf '%s\n' "$1"
  else
    newest_run
  fi
}

case "${1:-}" in
  start) start_run "${2:-$DEFAULT_RUNNER}" ;;
  watch)
    run_id="$(pick_run "${2:-}")"
    watch_run "$run_id"
    ;;
  logs)
    run_id="$(pick_run "${2:-}")"
    gh run view -R "$REPO" "$run_id" --log-failed
    ;;
  *)
    echo "Usage: $0 <macos|windows> start [runner] | watch [run-id] | logs [run-id]" >&2
    exit 2
    ;;
esac
