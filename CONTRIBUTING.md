# Contributing to Godhand Lazarus

Godhand Lazarus is in a quiet beta. We want outside help, but we want it to
land through a clear path instead of chaos.

## What To Contribute

Best early contributions:

- install and portability fixes
- documentation clarifications
- importer edge-case fixes
- validation and support tooling improvements
- issues labeled `good first issue` or `help wanted`

## Before You Start

1. Check [ROADMAP.md](ROADMAP.md) and existing issues.
2. Open or claim an issue before writing code for anything non-trivial.
3. Keep pull requests small and focused on one outcome.

During beta, maintainers keep merge control. We may ask you to reshape a change
into a smaller patch or route it through an issue first.

## Local Workflow

```bash
./scripts/install_local_stack.sh --tool all
python3 scripts/check_memory_stack.py --tool all
```

If you are touching install, ingest, or CLI integration code, also run the
narrowest acceptance check you can support locally:

```bash
./scripts/test_cli_integrations.sh --tool claude
./scripts/test_cli_integrations.sh --tool gemini
./scripts/test_cli_integrations.sh --tool codex
```

Do not burn API credits or CLI quota just to prove an unrelated docs change.

## Pull Request Rules

- Link the issue you are addressing.
- Explain what changed and how you tested it.
- Call out platform assumptions, especially around macOS, Docker, Qdrant, or CLI auth.
- Do not mix refactors with behavioral changes unless the refactor is required for the fix.

## Issue-First During Beta

We are intentionally running a curated beta:

- bug fixes should map to an issue
- new features should start as a discussion or issue
- roadmap work should be aligned with maintainers before large implementation

If you are unsure where something belongs, start in GitHub Discussions or read
[SUPPORT.md](SUPPORT.md).
