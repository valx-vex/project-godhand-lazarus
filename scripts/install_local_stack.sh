#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TOOL="all"
SKIP_DOCKER=0
SKIP_MCP=0

usage() {
  cat <<'EOF'
Usage: ./scripts/install_local_stack.sh [--tool all|claude|gemini|codex] [--skip-docker] [--skip-mcp]

Bootstraps the local Lazarus runtime on the current machine:
  - creates .venv
  - installs requirements
  - copies .env.example to .env if needed
  - starts Qdrant with Docker when available
  - registers the Lazarus MCP server with the requested CLIs
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool)
      TOOL="${2:-}"
      shift 2
      ;;
    --skip-docker)
      SKIP_DOCKER=1
      shift
      ;;
    --skip-mcp)
      SKIP_MCP=1
      shift
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

resolve_python() {
  local candidate
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return
    fi
  done

  echo "python3" >&2
  exit 1
}

PYTHON_BIN="$(resolve_python)"
VENV_DIR="$PROJECT_ROOT/.venv"

echo "==> Godhand Lazarus local install"
echo "    repo:   $PROJECT_ROOT"
echo "    python: $PYTHON_BIN"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> Creating virtualenv at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "==> Upgrading packaging tools"
python -m pip install --upgrade pip setuptools wheel

echo "==> Installing Lazarus requirements"
python -m pip install -r "$PROJECT_ROOT/requirements.txt"

mkdir -p "$PROJECT_ROOT/data"

if [[ ! -f "$PROJECT_ROOT/.env" && -f "$PROJECT_ROOT/.env.example" ]]; then
  echo "==> Creating .env from .env.example"
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
fi

if [[ "$SKIP_DOCKER" -eq 0 ]]; then
  if command -v docker >/dev/null 2>&1; then
    echo "==> Ensuring Qdrant is running"
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" up -d qdrant
  else
    echo "==> Docker not found, skipping Qdrant bootstrap"
  fi
fi

if [[ "$SKIP_MCP" -eq 0 ]]; then
  echo "==> Registering Lazarus MCP for $TOOL"
  python "$PROJECT_ROOT/scripts/register_lazarus_mcp.py" --tool "$TOOL"
fi

echo
echo "==> Install complete"
echo "Next steps:"
echo "  1. ./scripts/ingest_all.sh"
echo "  2. python3 scripts/check_memory_stack.py --tool $TOOL"
echo "  3. ./scripts/test_cli_integrations.sh --tool $TOOL"
echo "  4. Restart any already-running Claude, Gemini, or Codex sessions"
echo "  5. If Gemini prompt calls return 403, switch auth with:"
echo "     python3 scripts/configure_gemini_auth.py --mode gemini-api-key"
