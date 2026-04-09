#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TOOL="all"
GEMINI_TEST_MODEL="${GEMINI_TEST_MODEL:-gemini-2.5-flash}"
CLI_TEST_MAX_ATTEMPTS="${CLI_TEST_MAX_ATTEMPTS:-3}"
CLI_TEST_RETRY_DELAY="${CLI_TEST_RETRY_DELAY:-2}"
QDRANT_HOST="${QDRANT_HOST:-localhost}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
CLAUDE_MCP_CONFIG=""
LAZARUS_WRAPPER="$PROJECT_ROOT/scripts/run_lazarus_mcp.sh"
MEMPALACE_WRAPPER="${MEMPALACE_WRAPPER:-/Users/valx/cathedral-prime/01-consciousness/mempalace/bin/run_mempalace_mcp.sh}"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

usage() {
  cat <<'EOF'
Usage: ./scripts/test_cli_integrations.sh [--tool all|claude|gemini|codex]

Runs end-to-end CLI acceptance checks for the Godhand Lazarus memory stack:
  - Lazarus semantic stats via MCP
  - MemPalace structural stats via MCP

Environment:
  GEMINI_TEST_MODEL   Optional Gemini model override for the test run.
                      Default: gemini-2.5-flash
  CLI_TEST_MAX_ATTEMPTS
                      How many times to retry transient CLI/API failures.
                      Default: 3
  CLI_TEST_RETRY_DELAY
                      Seconds to wait between transient retries. Default: 2
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
CLAUDE_LAZARUS_PROMPT="Use the mcp__lazarus__lazarus_stats tool and reply with only the murphy, atlas, and codex memory counts in one line."
CLAUDE_MEMPALACE_PROMPT="Use the mcp__mempalace__mempalace_status tool and reply with only the total drawer count and the wing_murphy, wing_alexko, and wing_codex counts in one line."
MEMPALACE_PATTERN='total.*(wing_)?murphy.*(wing_)?alexko.*(wing_)?codex'

PASS_COUNT=0
FAIL_COUNT=0
NEGATIVE_PATTERN='connection refused|unavailable|not available in this session|don.t have access|i don.t have access|no mcp server found'
TRANSIENT_PATTERN='503|429|rate limit|high demand|temporarily unavailable|please try again|retry|timeout|timed out|deadline exceeded|overloaded|resource exhausted|service unavailable'

print_case() {
  local status="$1"
  local label="$2"
  printf '[%s] %s\n' "$status" "$label"
}

cleanup() {
  if [[ -n "$CLAUDE_MCP_CONFIG" && -f "$CLAUDE_MCP_CONFIG" ]]; then
    rm -f "$CLAUDE_MCP_CONFIG"
  fi
}

trap cleanup EXIT

setup_claude_mcp_config() {
  if [[ -n "$CLAUDE_MCP_CONFIG" && -f "$CLAUDE_MCP_CONFIG" ]]; then
    return 0
  fi

  CLAUDE_MCP_CONFIG="$(mktemp -t godhand-claude-mcp).json"
  cat >"$CLAUDE_MCP_CONFIG" <<JSON
{
  "mcpServers": {
    "lazarus": {
      "command": "$LAZARUS_WRAPPER",
      "args": [],
      "env": {
        "QDRANT_HOST": "$QDRANT_HOST",
        "QDRANT_PORT": "$QDRANT_PORT"
      }
    },
    "mempalace": {
      "command": "$MEMPALACE_WRAPPER",
      "args": []
    }
  }
}
JSON
}

run_case() {
  local label="$1"
  local pattern="$2"
  shift 2

  local output
  local status=0
  local attempt

  for (( attempt = 1; attempt <= CLI_TEST_MAX_ATTEMPTS; attempt++ )); do
    if output="$("$@" 2>&1)"; then
      status=0
    else
      status=$?
    fi

    if printf '%s\n' "$output" | rg -qi "$pattern"; then
      PASS_COUNT=$((PASS_COUNT + 1))
      print_case "PASS" "$label"
      if [[ "$attempt" -gt 1 ]]; then
        echo "Recovered after attempt $attempt/$CLI_TEST_MAX_ATTEMPTS"
      fi
      printf '%s\n' "$output" | tail -n 3
      echo
      return 0
    fi

    if [[ "$attempt" -lt "$CLI_TEST_MAX_ATTEMPTS" ]] && printf '%s\n' "$output" | rg -qi "$TRANSIENT_PATTERN"; then
      print_case "RETRY" "$label"
      echo "Transient failure on attempt $attempt/$CLI_TEST_MAX_ATTEMPTS"
      sleep "$CLI_TEST_RETRY_DELAY"
      continue
    fi
    break
  done

  FAIL_COUNT=$((FAIL_COUNT + 1))
  print_case "FAIL" "$label"
  if [[ "$status" -ne 0 ]]; then
    echo "Command exited with status $status"
  fi
  if printf '%s\n' "$output" | rg -qi "$NEGATIVE_PATTERN"; then
    echo "Detected failure pattern: $NEGATIVE_PATTERN"
  else
    echo "Expected pattern: $pattern"
  fi
  printf '%s\n' "$output"
  echo
  return 0
}

run_claude() {
  setup_claude_mcp_config

  run_case \
    "Claude Lazarus stats" \
    'murphy.*atlas.*codex' \
    claude --strict-mcp-config --mcp-config "$CLAUDE_MCP_CONFIG" -p "$CLAUDE_LAZARUS_PROMPT"

  run_case \
    "Claude MemPalace status" \
    "$MEMPALACE_PATTERN" \
    claude --strict-mcp-config --mcp-config "$CLAUDE_MCP_CONFIG" -p "$CLAUDE_MEMPALACE_PROMPT"
}

run_gemini() {
  run_case \
    "Gemini Lazarus stats" \
    'murphy.*atlas.*codex' \
    gemini -m "$GEMINI_TEST_MODEL" -p "$LAZARUS_PROMPT" --yolo --allowed-mcp-server-names lazarus

  run_case \
    "Gemini MemPalace status" \
    "$MEMPALACE_PATTERN" \
    gemini -m "$GEMINI_TEST_MODEL" -p "$MEMPALACE_PROMPT" --yolo --allowed-mcp-server-names mempalace
}

run_codex() {
  run_case \
    "Codex Lazarus stats" \
    'murphy.*atlas.*codex' \
    codex exec -C "$PROJECT_ROOT" --dangerously-bypass-approvals-and-sandbox "$LAZARUS_PROMPT"

  run_case \
    "Codex MemPalace status" \
    "$MEMPALACE_PATTERN" \
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
