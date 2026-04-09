# Godhand Lazarus MCP Install

## Recommended Path

Register Lazarus through the repo wrapper so each CLI points at the local
checkout instead of a hardcoded Cathedral-only path.

```bash
cd /path/to/project-godhand-lazarus
./scripts/install_local_stack.sh --tool all
```

That command:

- creates `.venv`
- installs Lazarus requirements
- starts Qdrant with Docker when available
- registers the Lazarus MCP server for Claude, Gemini, and Codex

## Register A Single CLI

```bash
python3 scripts/register_lazarus_mcp.py --tool claude
python3 scripts/register_lazarus_mcp.py --tool gemini
python3 scripts/register_lazarus_mcp.py --tool codex
```

## What Gets Registered

All three CLIs point to:

```text
scripts/run_lazarus_mcp.sh
```

That wrapper resolves the repo-local Python runtime and launches:

```text
mcp_server/lazarus_mcp.py
```

## Validate The Install

```bash
python3 scripts/check_memory_stack.py --tool all
./scripts/test_cli_integrations.sh --tool all
```

Expected for a full stack:

- Qdrant reachable on `localhost:6333`
- Lazarus MCP present in the selected CLI configs
- MemPalace detected if you are running the full layered stack
- continuity layer detected if you are using VexNet-style session sync
- Claude, Gemini, and Codex can each complete an actual Lazarus/MemPalace MCP call

## Gemini API-Key Mode

If Gemini sign-in works but prompt calls fail or the repo-local `.env` shadows
your home-level key, switch with:

```bash
python3 scripts/configure_gemini_auth.py --mode gemini-api-key
```

That helper updates `~/.gemini/settings.json` and syncs a repo-local
`.gemini/.env` when needed.

## MCP Tools

- `lazarus_summon`
- `lazarus_remember`
- `lazarus_rehydrate`
- `lazarus_stats`
