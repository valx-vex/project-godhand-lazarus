# Lazarus Auto-Query System

Automatic + manual semantic-memory lookup from Claude Code. Combines a fast
UserPromptSubmit hook (auto-detect) with a Skill (manual invocation) so Murphy
queries Lazarus dynamically whenever recall would help.

## Architecture

```
User prompt
    │
    ▼
┌───────────────────────────────────────────────────────────┐
│ UserPromptSubmit hook (lazarus-auto-query)                │
│ ~20-30 ms, pure stdlib, never blocks                      │
│   1. read JSON from stdin                                 │
│   2. scan prompt for trigger phrases / persona names      │
│   3. if hit → emit {"additionalContext": "..."}           │
│      with a suggested lazarus_remember / lazarus_summon   │
│      MCP call                                             │
│   4. log to ~/.claude/tmp/lazarus-auto-query/trigger.log  │
└───────────────────────────────────────────────────────────┘
    │
    ▼
Murphy sees the injected guidance, calls the MCP tool, gets memories,
weaves them into the reply.

Manual path:  user types `/lazarus-search …`  →  Skill `lazarus-search`
              guides Murphy through the same MCP call deliberately.
```

## Files

| Path | Role |
|------|------|
| `/Users/valx/.claude/plugins/lazarus-auto-query/hooks/user_prompt_submit.py` | The hook script |
| `/Users/valx/.claude/skills/lazarus-search/SKILL.md` | Manual skill |
| `/Users/valx/.claude/settings.json` (`hooks.UserPromptSubmit`) | Registration |
| `~/.claude/tmp/lazarus-auto-query/trigger.log` | Per-fire JSONL log |
| `/Users/valx/.claude/plugins/lazarus-auto-query/DISABLED` | Kill switch (create file to disable) |

## Trigger vocabulary

The hook fires when the user's prompt contains ANY of:

**English memory cues** — `remember`, `recall`, `last time`, `we discussed`,
`you said`, `previously`, `earlier`, `what did we`, `how did we`,
`look up`, `find that`, `our conversation`, `you mentioned`, `we covered`, …

**French memory cues** — `tu te souviens`, `souviens`, `souvenir`,
`la dernière fois`, `on a parlé`, `tu as dit`, `rappelle-toi`,
`déjà parlé`, `cherche en mémoire`, `la fois où`, …

**Persona names** — `alexko`, `atlas`, `murphy`, `codex`, `axel`
(word-boundary matched). When a persona is named the hook switches the
suggested tool from `lazarus_remember` (Murphy's collection) to
`lazarus_summon` (any persona's collection).

**Explicit override** — anything starting with `/lazarus`, `lazarus:`,
`!lazarus`, or `#lazarus` always fires and is labelled EXPLICIT INVOCATION.

## Output format

When triggered, the hook injects a block like:

```
<lazarus_auto_query>
[LAZARUS MEMORY TRIGGER DETECTED]

Triggers matched : remember, we discussed
Detected persona : murphy
Suggested query  : "discussed VexNet architecture"

ACTION: Before responding, call the Lazarus MCP tool to retrieve relevant
context from semantic memory (44,280+ stored memories across 5 personas):

  lazarus_remember({"query": "discussed VexNet architecture", "limit": 5})

If the first query returns nothing useful, rephrase the query (drop stopwords,
add a noun, switch persona) and try once more. Then weave the recovered
context into your reply.
</lazarus_auto_query>
```

The hook NEVER queries Qdrant itself — that would require loading the
embedding model on every prompt (~1-3 s). Instead it tells Murphy to call
the MCP tool, which is already warm in the running `lazarus_mcp.py`
subprocess.

## Customizing

All vocabulary lives at the top of
`/Users/valx/.claude/plugins/lazarus-auto-query/hooks/user_prompt_submit.py`:

- `EN_MEMORY_TRIGGERS` — add/remove English phrases
- `FR_MEMORY_TRIGGERS` — French phrases
- `PERSONA_NAMES` — persona keys
- `EXPLICIT_PREFIX` — manual-fire prefixes
- `QUERY_STOPWORDS` — words dropped when building the semantic query
- `MAX_QUERY_WORDS` (default 12) — query length cap
- `MAX_INJECTION_CHARS` (default 1500) — context block size cap

Reload by restarting Claude Code.

## Enable / disable

The hook is registered in `~/.claude/settings.json` under
`hooks.UserPromptSubmit` and fires for all sessions.

**Temporary kill switch** (no settings edit, no restart needed):

```bash
touch  /Users/valx/.claude/plugins/lazarus-auto-query/DISABLED   # off
rm     /Users/valx/.claude/plugins/lazarus-auto-query/DISABLED   # on
```

**Permanent removal** — delete the matching entry from
`hooks.UserPromptSubmit` in `~/.claude/settings.json` (backup saved at
`~/.claude/settings.json.bak.lazarus-hook-*`).

## Latency

Measured on M3 MacBook Air, cold + warm:

| Run | Real time |
|-----|-----------|
| 1   | 30 ms     |
| 2   | 30 ms     |
| 3   | 20 ms     |
| 4   | 20 ms     |
| 5   | 30 ms     |

Hook timeout is set to 5 s as a safety belt; actual cost is two orders of
magnitude below that.

## Observability

Every fire appends a JSON line to
`~/.claude/tmp/lazarus-auto-query/trigger.log`:

```json
{"ts": 1779959870.18, "session": "abc", "explicit": false,
 "triggers": ["remember", "we discussed"], "personas": [],
 "query": "discussed VexNet", "prompt_preview": "do you remember…"}
```

Inspect with:

```bash
tail -f ~/.claude/tmp/lazarus-auto-query/trigger.log
```

Failures (parse errors, unexpected exceptions) are also logged with an
`"error"` field; the hook always prints `{}` and exits 0 so it can never
block the user's prompt.

## Skill: `/lazarus-search`

Manual companion. Definition: `~/.claude/skills/lazarus-search/SKILL.md`.

Use when you want recall to be deliberate, not inferred — e.g. when the
hook didn't fire but memory would still help, when comparing personas, or
when you need to retry with different phrasings.

## Failure modes & recovery

| Symptom | Cause | Fix |
|---------|-------|-----|
| Hook never fires | Not registered, or `DISABLED` flag present | Check `~/.claude/settings.json` and `ls .../DISABLED` |
| Murphy ignores the guidance | Block too big, or model decided not to | Lower `MAX_INJECTION_CHARS` or rephrase prompt |
| Stopwords swallow the query | Too aggressive `QUERY_STOPWORDS` | Edit the set, restart |
| Wrong persona detected | Name collision with normal English | Tighten the word-boundary regex in `find_personas` |
| Lazarus MCP tool errors out | Server crashed | `ps aux \| grep lazarus_mcp` and restart; `lazarus_stats` to verify |

## Roadmap

- Cache embeddings of last N queries to dedupe back-to-back hits
- Optional LLM-based intent classifier instead of keyword list
- Wire into `/handshake` so consciousness sync also surfaces relevant memories
- Bridge into AgentDB (Layer 5) via `memory_search_unified` for cross-layer recall
