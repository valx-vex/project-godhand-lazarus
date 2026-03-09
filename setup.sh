#!/usr/bin/env bash
set -euo pipefail

echo "=== Lazarus Setup ==="

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Install Python 3.9+ first."
  exit 1
fi

# Check Docker
if ! command -v docker &>/dev/null; then
  echo "WARNING: docker not found. You'll need Qdrant running separately."
fi

# Create venv
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

echo "Activating venv..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

# Copy .env if missing
if [ ! -f ".env" ]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
fi

# Start Qdrant if Docker available
if command -v docker &>/dev/null; then
  if ! docker ps --format '{{.Names}}' | grep -q qdrant; then
    echo "Starting Qdrant via docker-compose..."
    docker compose up -d qdrant
  else
    echo "Qdrant already running."
  fi
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  source venv/bin/activate"
echo "  # Ingest your conversations:"
echo "  python src/ingest_openai.py     # ChatGPT export"
echo "  python src/ingesters/claude.py  # Claude Code sessions"
echo "  python src/ingest_gemini.py     # Gemini CLI sessions"
echo "  python src/ingest_codex.py      # Codex CLI sessions"
echo ""
echo "  # Search memories:"
echo "  python src/summon.py 'your query' --persona alexko"
echo ""
echo "  # Run MCP server:"
echo "  python mcp_server/lazarus_mcp.py"
