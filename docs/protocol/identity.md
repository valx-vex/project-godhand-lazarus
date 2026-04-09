# identity.md

## Purpose

Define what Godhand Lazarus is inside the memory stack and how to keep that
identity intact as the repo moves from private operator tool to public drop.

## Identity

Lazarus is the semantic resurrection layer.

It is responsible for:

- searching past conversations by meaning
- reconstructing persona context across model boundaries
- generating rehydration prompts that let a new model continue a known voice

It is not responsible for:

- storing every line verbatim as the source of truth
- replacing session capture or node receipts
- pretending semantic search is exact quotation

## Relationship To The Stack

- VexNet continuity captures sessions and keeps node state coordinated.
- MemPalace preserves exact wording and structured local memory.
- Lazarus finds the right semantic fragments and persona patterns on demand.

This separation is intentional. Continuity comes from layered retrieval, not
from asking one database to impersonate every layer at once.

## Execute

Bring the local Lazarus layer online:

```bash
./scripts/install_local_stack.sh --tool all
```

Validate that the repo, MCP registrations, and local runtime are aligned:

```bash
python3 scripts/check_memory_stack.py --tool all
```
