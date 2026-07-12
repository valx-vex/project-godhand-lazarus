# Lazarus Debugging Notes

Date: 2026-05-28

## Hook Injection

Root cause: the hook detected prompts correctly, but emitted the older
top-level JSON shape:

```json
{"additionalContext": "..."}
```

Claude Code's current structured hook output expects:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "..."
  }
}
```

Fix:

- `user_prompt_submit.py` now emits `hookSpecificOutput.additionalContext`.
- The guidance now includes a visible acknowledgement instruction, so Murphy
  should briefly say that a Lazarus cue was detected before searching memory.
- Added the missing French trigger `souviens-toi`.

Manual test:

```bash
printf '{"session_id":"smoke","prompt":"Souviens-toi de VexNet"}' \
  | python3 ~/.claude/plugins/lazarus-auto-query/hooks/user_prompt_submit.py \
  | python3 -m json.tool
```

Expected: JSON with `hookSpecificOutput.hookEventName = UserPromptSubmit` and
an `additionalContext` block containing `VISIBLE ACK`.

## MCP Path

Root cause: two config surfaces disagreed.

- `~/.claude/settings.json` had the new repo path.
- Claude Code's user-scope MCP registry in `~/.claude.json` still had the old
  deployed path.

`claude mcp get lazarus` and `claude mcp list` used `~/.claude.json`, so the
running MCP server followed the old path even though `settings.json` looked
correct.

Fix:

```bash
claude mcp remove lazarus -s user
claude mcp add lazarus -s user \
  --env QDRANT_HOST=localhost \
  --env QDRANT_PORT=6333 \
  -- /Users/valx/vex/repos/project-godhand-lazarus/scripts/run_lazarus_mcp.sh
```

A backup was made before the change:

```bash
~/.claude.json.bak.lazarus-mcp-*
```

Verification:

```bash
claude mcp get lazarus
claude mcp list | grep lazarus
lazarus status --json | jq '.mcp'
ps auxww | grep lazarus_mcp.py
```

Expected: all active Lazarus MCP configuration points to
`/Users/valx/vex/repos/project-godhand-lazarus/`.
