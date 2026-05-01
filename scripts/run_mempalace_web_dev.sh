#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
  echo "Missing $PROJECT_ROOT/.venv. Run scripts/install_mempalace_web_ui.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$PROJECT_ROOT/.venv/bin/activate"

cd "$PROJECT_ROOT"
python -m uvicorn web_api.main:app --host 127.0.0.1 --port 8000 --reload &
API_PID=$!

cleanup() {
  kill "$API_PID" >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

cd "$PROJECT_ROOT/web"
npm run dev -- --host 127.0.0.1 --port 5173
