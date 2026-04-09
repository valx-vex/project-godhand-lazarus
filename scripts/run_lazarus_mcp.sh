#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

resolve_python() {
  if [[ -n "${LAZARUS_PYTHON:-}" && -x "${LAZARUS_PYTHON}" ]]; then
    printf '%s\n' "${LAZARUS_PYTHON}"
    return
  fi

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

  echo "Unable to resolve a Python runtime for Lazarus." >&2
  exit 1
}

PYTHON_BIN="$(resolve_python)"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

export HF_HUB_DISABLE_TELEMETRY="${HF_HUB_DISABLE_TELEMETRY:-1}"

cd "$PROJECT_ROOT"
exec "$PYTHON_BIN" "$PROJECT_ROOT/mcp_server/lazarus_mcp.py" "$@"
