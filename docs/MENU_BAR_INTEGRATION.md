# Lazarus Menu Bar Integration

Date: 2026-05-28

Lazarus Layer 2 is surfaced inside `VexNet Control.app` alongside VexNet
Layer 4 and remote-volume status.

## CLI Contract

The menu app reads Lazarus through:

```bash
~/bin/lazarus status --json
```

The JSON includes:

- `qdrant.ok` and `qdrant.base_url`
- `daemon.running`, `daemon.pid`, `daemon.label`
- `mcp.ok`, `mcp.command`, `mcp.expected`
- `memories.collections`, `memories.by_persona`, `memories.total`
- `sync.last_sync` and per-persona sync timestamps
- `logs.daemon`

The plain-text `lazarus status` and `lazarus stats` outputs remain available
for humans. `lazarus stats --json` exposes counts for scripts.

## Menu Behavior

`VexNet Control.app` now has a compact layer picker:

- `Overview`: VexNet, Lazarus, remote volumes, and last action.
- `VexNet`: existing Layer 4 freshness and refresh controls.
- `Lazarus`: memory counts, daemon state, Qdrant, MCP path, last sync, and
  Layer 2 actions.

Lazarus actions:

- Force Sync Now: `lazarus sync`
- Restart Daemon: `lazarus daemon restart`
- Run Health Check: `lazarus health`
- View Logs: opens `daemon/lazarus_sync.log`
- Daemon Control: start/stop

The menu icon aggregates VexNet, Lazarus core status, and last-action state.
Remote volumes remain visible inside the panel but do not force the top-level
memory-control icon into warning state.

## Verification

```bash
lazarus status --json | jq .
vexnet menu-agent
vexnet health
```

Open the menu bar panel and confirm the Lazarus tab shows the same total as:

```bash
lazarus stats
```
