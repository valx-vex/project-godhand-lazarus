# drift_checks.md

## Purpose

Prevent the memory stack from silently drifting across nodes or being flattened
into a single-store story that hides failure modes.

## Checks

### Config Drift

Verify on every node:

- `~/.claude/settings.json` contains `mempalace`
- `~/.claude/settings.local.json` contains Stop + PreCompact hooks
- `~/.gemini/settings.json` contains `mempalace`
- `~/.codex/config.toml` contains `[mcp_servers.mempalace]`

### Runtime Drift

Verify:

- `mempalace_doctor.py --check-mcp` resolves to `~/.mempalace/venv312/bin/python3`
- wrappers do not prefer the synced shared `.venv312`

### Corpus Drift

Verify:

- all nodes report the same drawer totals after seeding
- representative queries return the same wing-specific memories

### Boundary Drift

Verify:

- Lazarus still points to semantic/Qdrant flows
- MemPalace still owns verbatim local memory
- Codex hooks remain off unless deliberately enabled

## Sacred Flame Check

Run the repo-native validator:

```bash
python3 scripts/check_memory_stack.py --tool all
```

Scoring model:

- repo assets + MCP wrapper present
- Qdrant reachable
- selected CLI configs point to the repo wrapper
- MemPalace detected for the verbatim layer
- continuity detected for the capture layer

Interpretation:

- `10.0/10`: full layered stack
- `7.0-9.9`: Lazarus is healthy, but one supporting layer is missing or drifting
- `<7.0`: repair before claiming continuity integrity
