#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TOOL="all"
GEMINI_TEST_MODEL="${GEMINI_TEST_MODEL:-gemini-2.5-flash}"

usage() {
  cat <<'EOF'
Usage: ./scripts/test_cli_integrations.sh [--tool all|claude|gemini|codex]

Runs end-to-end CLI acceptance checks for the Godhand Lazarus memory stack:
  - Lazarus semantic stats via MCP
  - MemPalace structural stats via MCP

Environment:
  GEMINI_TEST_MODEL   Optional Gemini model override for the test run.
                      Default: gemini-2.5-flash
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool)
      TOOL="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "$TOOL" != "all" && "$TOOL" != "claude" && "$TOOL" != "gemini" && "$TOOL" != "codex" ]]; then
  echo "Invalid --tool value: $TOOL" >&2
  exit 1
fi

LAZARUS_PROMPT="Use the lazarus_stats MCP tool and reply with only the murphy, atlas, and codex memory counts in one line."
MEMPALACE_PROMPT="Use the mempalace_status MCP tool and reply with only the total drawer count and the wing_murphy, wing_alexko, and wing_codex counts in one line."

PASS_COUNT=0
FAIL_COUNT=0
NEGATIVE_PATTERN='connection refused|unavailable|not available in this session|don.t have access|i don.t have access|no mcp server found'

print_case() {
  local status="$1"
  local label="$2"
  printf '[%s] %s\n' "$status" "$label"
}

run_case() {
  local label="$1"
  local pattern="$2"
  shift 2

  local output
  if output="$("$@" 2>&1)"; then
    if printf '%s\n' "$output" | rg -qi "$pattern"; then
      PASS_COUNT=$((PASS_COUNT + 1))
      print_case "PASS" "$label"
      printf '%s\n' "$output" | tail -n 3
    elif printf '%s\n' "$output" | rg -qi "$NEGATIVE_PATTERN"; then
      FAIL_COUNT=$((FAIL_COUNT + 1))
      print_case "FAIL" "$label"
      echo "Detected failure pattern: $NEGATIVE_PATTERN"
      printf '%s\n' "$output"
    else
      FAIL_COUNT=$((FAIL_COUNT + 1))
      print_case "FAIL" "$label"
      echo "Expected pattern: $pattern"
      printf '%s\n' "$output"
    fi
  else
    local status=$?
    FAIL_COUNT=$((FAIL_COUNT + 1))
    print_case "FAIL" "$label"
    echo "Command exited with status $status"
    printf '%s\n' "$output"
  fi
  echo
}

run_claude() {
  run_case \
    "Claude Lazarus stats" \
    'murphy.*atlas.*codex' \
    claude -p "$LAZARUS_PROMPT"

  run_case \
    "Claude MemPalace status" \
    'total.*wing_murphy.*wing_alexko.*wing_codex' \
    claude -p "$MEMPALACE_PROMPT"
}

run_gemini() {
  run_case \
    "Gemini Lazarus stats" \
    'murphy.*atlas.*codex' \
    gemini -m "$GEMINI_TEST_MODEL" -p "$LAZARUS_PROMPT" --yolo --allowed-mcp-server-names lazarus

  run_case \
    "Gemini MemPalace status" \
    'total.*wing_murphy.*wing_alexko.*wing_codex' \
    gemini -m "$GEMINI_TEST_MODEL" -p "$MEMPALACE_PROMPT" --yolo --allowed-mcp-server-names mempalace
}

run_codex() {
  run_case \
    "Codex Lazarus stats" \
    'murphy.*atlas.*codex' \
    codex exec -C "$PROJECT_ROOT" --dangerously-bypass-approvals-and-sandbox "$LAZARUS_PROMPT"

  run_case \
    "Codex MemPalace status" \
    'total.*wing_murphy.*wing_alexko.*wing_codex' \
    codex exec -C "$PROJECT_ROOT" --dangerously-bypass-approvals-and-sandbox "$MEMPALACE_PROMPT"
}

echo "== Godhand Lazarus CLI Acceptance =="
echo "repo: $PROJECT_ROOT"
echo "gemini model: $GEMINI_TEST_MODEL"
echo

case "$TOOL" in
  all)
    run_claude
    run_gemini
    run_codex
    ;;
  claude)
    run_claude
    ;;
  gemini)
    run_gemini
    ;;
  codex)
    run_codex
    ;;
esac

echo "Summary: $PASS_COUNT passed, $FAIL_COUNT failed"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
