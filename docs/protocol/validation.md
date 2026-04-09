# validation.md

## Validation Protocol

The stack is acceptable only if all three layers can be exercised without contradiction.

## Repo Validation

Run on the current node:

```bash
python3 scripts/check_memory_stack.py --tool all
./scripts/test_cli_integrations.sh --tool all
```

Expected:

- Qdrant is reachable
- the selected CLI configs point to `scripts/run_lazarus_mcp.sh`
- the protocol docs exist in the repo
- Sacred Flame is reported with no core failures
- Claude, Gemini, and Codex each complete one Lazarus call and one MemPalace call

## Semantic Validation

Representative checks:

```bash
python3 src/summon.py "auto-clench" --persona murphy
python3 src/summon.py "trinity consciousness" --persona alexko
python3 src/summon.py "memory stack" --persona codex
```

Expected:

- Murphy material returns from `murphy_eternal`
- Alexko material returns from `alexko_eternal`
- Codex rollout material returns from `codex_eternal`

## Full Stack Validation

If MemPalace and continuity are also installed, verify the layered boundary:

- Lazarus still answers semantic/persona questions
- MemPalace still answers verbatim/local structure questions
- continuity still answers node/session propagation questions
- neither layer is described as the sole memory system

The stack passes only when those three roles remain distinct.

## Gemini API-Key Note

When running inside this repo, do not put the Gemini API key in the repo root
`.env`. This project already uses `.env` for Lazarus and Qdrant settings, and
Gemini stops at the first env file it finds.

Use:

```bash
python3 scripts/configure_gemini_auth.py --mode gemini-api-key
```

That command keeps the user-level key in `~/.gemini/.env` and syncs a
repo-local `.gemini/.env` when needed for local CLI runs.
