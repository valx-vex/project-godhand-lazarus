#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

resolve_python() {
  local candidate
  for candidate in \
    "$PROJECT_ROOT/.venv/bin/python" \
    "$PROJECT_ROOT/venv/bin/python" \
    "$(command -v python3 2>/dev/null || true)"
  do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  echo "Unable to resolve a Python runtime for Lazarus ingestion." >&2
  exit 1
}

PYTHON_BIN="$(resolve_python)"
OPENAI_EXPORT_PATH="${LAZARUS_DATA_FILE:-$PROJECT_ROOT/data/conversations.json}"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

run_ingest() {
  local label="$1"
  local script="$2"
  echo "==> $label"
  "$PYTHON_BIN" "$PROJECT_ROOT/$script"
}

if [[ -f "$OPENAI_EXPORT_PATH" ]]; then
  export LAZARUS_DATA_FILE="$OPENAI_EXPORT_PATH"
  echo "==> ChatGPT export source: $LAZARUS_DATA_FILE"
  run_ingest "Ingesting ChatGPT export" "src/ingest_openai.py"
else
  echo "==> Skipping ChatGPT export ($OPENAI_EXPORT_PATH not present)"
fi

run_ingest "Ingesting Claude sessions" "src/ingest_claude.py"
run_ingest "Ingesting Gemini sessions" "src/ingest_gemini.py"
run_ingest "Ingesting Codex sessions" "src/ingest_codex.py"

echo
echo "==> Ingestion complete"
