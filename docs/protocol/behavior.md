# behavior.md

## Retrieval Behavior

When a tool or agent needs memory:

1. Use Lazarus when the problem is semantic.
2. Use MemPalace when exact wording, exact structure, or local transcript fidelity matters.
3. Use VexNet continuity when the question is about what happened on which node or in which recent session.

## Behavioral Rules

- Do not collapse semantic and verbatim stores into one database.
- Do not claim exact wording from Lazarus alone.
- Do not claim global persona continuity from MemPalace alone.
- Prefer layered retrieval over single-store certainty.

## Practical Rule

Ask:

- "What was this about?" -> Lazarus
- "What were the exact words?" -> MemPalace
- "Where did this happen and how did it propagate?" -> VexNet continuity

## Execute

Seed the semantic layer from the current machine:

```bash
./scripts/ingest_all.sh
```

Run a semantic lookup after ingestion:

```bash
python3 src/summon.py "trinity consciousness" --persona alexko
python3 src/summon.py "auto-clench" --persona murphy
```

Use those results as semantic recall, then move to MemPalace if you need exact
wording.
