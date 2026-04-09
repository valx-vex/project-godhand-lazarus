#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT/support-bundles"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_FILE=""

usage() {
  cat <<'EOF'
Usage: ./scripts/collect_support_bundle.sh [--output-dir PATH]

Collect a sanitized Markdown support bundle for GitHub issues and beta support.

The bundle avoids secrets by design and captures:
  - host and repo basics
  - tool versions when available
  - Qdrant reachability
  - Godhand Lazarus drift-check output

EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="${2:-}"
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

mkdir -p "$OUTPUT_DIR"
OUTPUT_FILE="$OUTPUT_DIR/support-bundle-$TIMESTAMP.md"

sanitize() {
  sed \
    -e "s|$HOME|~|g" \
    -e 's/[A-Za-z0-9_]*API_KEY=[^[:space:]]\\+/API_KEY=[REDACTED]/g' \
    -e 's/gho_[A-Za-z0-9_]\\+/gho_[REDACTED]/g'
}

capture() {
  local title="$1"
  shift
  {
    echo "## $title"
    echo
    echo '```text'
    if "$@" 2>&1 | sanitize; then
      :
    else
      echo "[command exited non-zero]"
    fi
    echo '```'
    echo
  } >>"$OUTPUT_FILE"
}

compose_ps() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    docker compose ps
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose ps
    return 0
  fi
  echo "docker compose not available"
}

repo_state() {
  echo "branch: $(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unavailable)"
  echo "commit: $(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo unavailable)"
  echo "version: $(cat "$PROJECT_ROOT/VERSION" 2>/dev/null || echo unavailable)"
}

tool_versions() {
  command -v python3 >/dev/null 2>&1 && printf 'python3: %s\n' "$(python3 --version 2>&1)"
  command -v docker >/dev/null 2>&1 && printf 'docker: %s\n' "$(docker --version 2>&1)"
  command -v claude >/dev/null 2>&1 && printf 'claude: %s\n' "$(claude --version 2>&1 | head -n 1)"
  command -v gemini >/dev/null 2>&1 && printf 'gemini: %s\n' "$(gemini --version 2>&1 | head -n 1)"
  command -v codex >/dev/null 2>&1 && printf 'codex: %s\n' "$(codex --version 2>&1 | head -n 1)"
}

{
  echo "# Godhand Lazarus Support Bundle"
  echo
  echo "- Generated (UTC): $TIMESTAMP"
  echo "- Repo: $(printf '%s' "$PROJECT_ROOT" | sanitize)"
  echo "- Sanitization: home path normalized, obvious token patterns redacted, secrets omitted by design"
  echo
} >"$OUTPUT_FILE"

capture "Host" uname -a

if command -v sw_vers >/dev/null 2>&1; then
  capture "macOS" sw_vers
fi

capture "Repository State" repo_state
capture "Tool Versions" tool_versions
capture "Qdrant Process State" compose_ps
capture "Drift Check" python3 "$PROJECT_ROOT/scripts/check_memory_stack.py" --tool all

echo "Wrote support bundle: $OUTPUT_FILE"
