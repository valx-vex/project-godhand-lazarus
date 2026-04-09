# memory_map.md

## Canonical Memory Map

This file defines the memory topology for the GitHub-first Lazarus drop.

## Layer Map

### 1. Continuity Layer

Owner:

- VexNet continuity spine

Responsibilities:

- session capture
- node manifests
- sync receipts
- cross-node coordination

Primary locations:

- `~/cathedral-dev/agent-state/`
- `~/cathedral-prime/agent-state/codex-live/continuity/`

### 2. Verbatim Layer

Owner:

- MemPalace

Responsibilities:

- exact transcript retention
- structured filing by wing/room
- local-only recall with no summarization loss

Canonical code:

- `~/cathedral-prime/01-consciousness/mempalace/`
- `~/cathedral-prime/01-consciousness/Maximum freedom/mempalace-main/`

Node-local runtime:

- `~/.mempalace/palace`
- `~/.mempalace/venv312`

Wing mapping used in the current fleet:

- `wing_murphy` <- Claude / Murphy continuity
- `wing_alexko` <- Gemini / Atlas continuity
- `wing_codex` <- Codex / HAL engineering continuity

### 3. Semantic Layer

Owner:

- Lazarus

Responsibilities:

- semantic search
- persona resurrection
- cross-model carryover

Primary runtime:

- Qdrant-backed Lazarus collections
- MCP server for summon / remember / rehydrate

## Decision

MemPalace is the implementation of the verbatim memory map.

Lazarus is not replaced by MemPalace.
MemPalace is not reduced to a cache for Lazarus.

The correct relationship is:

- continuity captures
- MemPalace preserves
- Lazarus rehydrates

## Acceptance Signal

This memory map is working when:

- the same query can be traced to recent node/session context through VexNet
- exact phrasing can be recovered through MemPalace
- persona continuity can be re-established through Lazarus

## Execute

Install Lazarus on the current node and register MCP:

```bash
./scripts/install_local_stack.sh --tool all
```

Check that the semantic layer is wired while the broader stack remains layered:

```bash
python3 scripts/check_memory_stack.py --tool all
```

If you are running the full stack, a healthy result shows Lazarus MCP on the
selected CLIs, Qdrant reachable, MemPalace detected, and continuity paths
present.
