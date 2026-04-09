# handoff.md

## Handoff Goal

Make another agent or model capable of continuing work without flattening the memory stack.

## Required Handoff Items

Include:

- the active node
- the relevant continuity manifest or session reference
- the MemPalace wing/room or query that recovers exact wording
- the Lazarus persona or query that recovers semantic lineage

## Minimal Handoff Template

- node:
- current task:
- recent continuity source:
- MemPalace query:
- Lazarus query:
- validation command:
- known risks:

## Rule

Never hand off with only a semantic summary if the next agent may need exact language.

## Execute

Before handoff, capture the current stack state:

```bash
python3 scripts/check_memory_stack.py --tool all
```

Use a handoff packet that points to both semantic and verbatim retrieval:

- node: current machine or SSH target
- current task: current operator goal
- recent continuity source: latest VexNet receipt or session path
- MemPalace query: exact wording retrieval path
- Lazarus query: semantic/persona retrieval path
- validation command: `python3 scripts/check_memory_stack.py --tool all`
- known risks: model drift, missing export, stale node restart
