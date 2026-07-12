# Lazarus Control CLI — Design

Modeled on `vexnet` (`/Users/valx/bin/vexnet` → `/Users/valx/.vex/vexnet-control/venv/bin/python -m vexnet_control.cli`).

## Goals

- Single global entrypoint (`lazarus`) for inspecting and controlling Layer 2 memory.
- Thin wrapper over existing scripts — no duplication of ingestion logic.
- Symlinked into `~/bin/` for global access.
- Suitable for menu-bar integration (machine-readable output paths planned).

## Architecture

```
~/bin/lazarus                                  # symlink
  → project-godhand-lazarus/scripts/run_lazarus_cli.sh   # venv resolver
    → project-godhand-lazarus/cli/lazarus_cli.py         # argparse CLI
        ├─ Qdrant HTTP API (localhost:6333) — counts, health
        ├─ launchctl                          — daemon control
        ├─ ~/.claude/settings.json            — MCP registration check
        ├─ scripts/check_memory_stack.py      — health subcommand
        ├─ scripts/ingest_all.sh              — ingest subcommand
        └─ daemon/install_daemon.sh           — daemon install
```

Single-file Python (~180 LOC, stdlib only — no extra deps). Bash wrapper resolves the project `.venv` like `run_lazarus_mcp.sh`, and dereferences symlinks so `~/bin/lazarus` works.

## Commands

| Command | Purpose |
|---|---|
| `lazarus status` | One-screen overview: Qdrant up, daemon running, MCP registered, per-persona counts, TOTAL. Exit 0 iff all green. |
| `lazarus stats` | Sorted table of all collections + grand total. |
| `lazarus health [...]` | Delegate to `scripts/check_memory_stack.py` (drift checks, Sacred Flame). |
| `lazarus ingest` | Run `scripts/ingest_all.sh` for full re-ingestion. |
| `lazarus sync` | `launchctl kickstart -k gui/$UID/com.vex.lazarus.sync` — force daemon run. |
| `lazarus daemon {start\|stop\|restart\|install\|logs}` | Lifecycle for the LaunchAgent. |

## Personas Tracked

`alexko`, `murphy`, `atlas`, `codex`, `axel`, `roundtable`, `scrolls` (collections suffixed `_eternal`). Missing collections render as `MISSING` rather than erroring.

## Exit Codes

- `status`: 0 = all systems green, 1 = any degraded.
- `health`: passthrough from `check_memory_stack.py`.
- All others: 0 on success, 1 on missing prerequisite.

## Menu-Bar Integration Plan

Menu bar agent should shell to `lazarus status` (or call `cli/lazarus_cli.py` directly) and parse fixed-format output. A future `--json` flag would emit:

```json
{
  "qdrant": true,
  "daemon": {"running": true, "pid": "69532"},
  "mcp": {"ok": true, "command": "..."},
  "memories": {"alexko": 28714, "murphy": 9749, ...},
  "total": 44280
}
```

Recommendation for `lazarus-menu` agent: add `--json` mode, then the menu bar polls every 30s.

## Hook System Integration

Hooks (Stop/SessionEnd) should drop conversation transcripts into a queue dir watched by `daemon/lazarus_sync_daemon.py`. CLI gains `lazarus queue {list,clear}` once the queue path is defined. See `lazarus-hook-builder` task.
