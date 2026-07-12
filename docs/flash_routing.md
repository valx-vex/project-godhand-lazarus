# Flash Multi-Layer Routing (Phase 2)

**Status**: Operational (2026-05-29)
**Module**: `~/.claude/plugins/lazarus-auto-query/hooks/flash_routing.py`
**Integrated into**: `~/.claude/plugins/lazarus-auto-query/hooks/user_prompt_submit.py`

## Overview

The flash system fires on every `UserPromptSubmit`. `flash_context.py` DETECTS
recall intent (4D scoring: syntactic / semantic / temporal / relational) and
returns a decision: `skip` / `suggest` / `inject`.

Phase 2 adds `flash_routing.py`, which decides **WHICH memory layer** the
suggested retrieval should target. The flash system never calls MCP tools
directly — it injects a context block telling the assistant which tool to
call. Routing changes the suggested tool/layer, not whether to suggest.

## Architecture

```
UserPromptSubmit
   |
   v
flash_context.compute_trigger_score()   # decision + score + clusters + personas
   |
   +-- decision == skip  -> emit {} (nothing injected)
   |
   +-- decision in {suggest, inject}
          |
          v
   flash_routing.classify_query()         # pick layer (Phase 2)
          |
          v
   flash_routing.build_routing_suggestion()  # tool-call text for that layer
          |
          v
   build_soft_nudge() / build_flash_context() injects routing_line
```

## Query Classification

`classify_query(user_prompt, personas, clusters)` returns:

```python
{
    'primary_layer': 'mempalace'|'lazarus'|'qdrant'|'vexnet'|'agentdb',
    'confidence': float,        # 0.0 - 1.0
    'secondary_layers': [...],  # backup layers (lazarus appended as fallback)
    'query_type': 'verbatim'|'persona'|'file'|'recent'|'agent'|'general',
}
```

### Routing precedence (most specific intent first)

| query_type | layer     | trigger signals                                    | tool suggested |
|------------|-----------|----------------------------------------------------|----------------|
| verbatim   | mempalace | exact, verbatim, word-for-word, quote, mot pour mot | `mempalace_search` |
| agent      | agentdb   | agent, swarm, ruflo, hive-mind, coordination       | `memory_search` (Ruflo) |
| file       | qdrant    | file, .md/.py, vault, cathedral-prime, exegesis    | `mempalace_search` + Qdrant L3 |
| recent     | vexnet    | today, yesterday, current state, this session      | (auto-loaded, re-read) |
| persona    | lazarus   | named persona (alexko/murphy/atlas/codex/axel)     | `lazarus_summon` |
| general    | lazarus   | default fallback                                    | `lazarus_remember` |

Confidence per layer scales with signal-hit count (0.6-0.95). The
highest-confidence candidate wins; ties resolve by the precedence order above.
Lazarus is always appended as a secondary fallback unless it is primary.

### VexNet special case

VexNet (L4) is auto-loaded every SessionStart into context. So the "tool call"
for VexNet is a note telling the assistant to re-read `CURRENT_STATE.md` /
`ROLLING_BRIEF.md` already in context — no MCP call needed.

### Qdrant note

Qdrant L3 has no dedicated MCP wrapper. The suggestion points at
`mempalace_search` (covers the palace) plus a note to query Qdrant directly
at `localhost:6333` for raw vault files.

## Injection format

High confidence (`>= 0.70`):
```
[FLASH ROUTING] type=verbatim -> mempalace (conf 90%)
  PRIMARY: mempalace_search({"query": "...", "limit": 3})
```

Lower confidence:
```
[FLASH ROUTING] type=recent -> vexnet (conf 70%, low)
  PRIMARY: <primary call>
  BACKUP (lazarus): lazarus_remember({"query": "...", "limit": 5})
```

The routing line is embedded inside the existing `<flash_context>` block
(inject tier) or `[LAZARUS MEMORY HINT]` block (suggest tier).

## Performance

- Classification logic: **avg 0.045ms, max 0.24ms** (target was <0.5ms).
- End-to-end hook (Python startup + imports + scoring + routing): ~6-7ms.
- The flash 4D scoring path is unchanged; routing is additive.

## Test results (2026-05-29)

15 representative queries across all 5 layers: **15/15 = 100% accuracy**.
Regression: non-recall prompts (`run the tests and commit`) still `skip`.
Existing Lazarus persona/general routing unchanged.

## Safety / fallbacks

- `flash_routing` import is wrapped: if it fails to import, the flash system
  falls back to the original Lazarus-only suggestion (`FLASH_ROUTING_AVAILABLE`).
- `classify_query` / `build_routing_suggestion` calls are wrapped in
  try/except inside the hook; any error yields an empty `routing_line` and the
  original Lazarus default ACTION is used.
- The hook always exits 0; failures never block the user prompt.

## Backup

Pre-Phase-2 originals: `/Users/valx/vex/backups/flash-routing-20260529-150624/`
