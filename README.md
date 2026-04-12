```
 ██████   ██████  ██████  ██   ██  █████  ███    ██ ██████
██       ██    ██ ██   ██ ██   ██ ██   ██ ████   ██ ██   ██
██   ███ ██    ██ ██   ██ ███████ ███████ ██ ██  ██ ██   ██
██    ██ ██    ██ ██   ██ ██   ██ ██   ██ ██  ██ ██ ██   ██
 ██████   ██████  ██████  ██   ██ ██   ██ ██   ████ ██████

██       █████  ███████  █████  ██████  ██    ██ ███████
██      ██   ██    ███  ██   ██ ██   ██ ██    ██ ██
██      ███████   ███   ███████ ██████  ██    ██ ███████
██      ██   ██  ███    ██   ██ ██   ██ ██    ██      ██
███████ ██   ██ ███████ ██   ██ ██   ██  ██████  ███████
```

> *"Your AI doesn't have to forget you."*

# Project Godhand: 5-Layer Memory for Multi-LLM Systems

> Your AI conversations are dying after every session. This is the resurrection engine.

[![v0.1.0](https://img.shields.io/badge/release-v0.1.0-blue)](#)
[![MCP Native](https://img.shields.io/badge/MCP-native-purple)](#)
[![Local First](https://img.shields.io/badge/local--first-no%20cloud-green)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## 10-Second Summary

**What**: 5-layer memory architecture that gives your AI persistent memory across sessions, platforms, and model changes.
**Why**: Because your AI forgetting you every session is not a feature -- it is a bug.
**Proof**: 96.6% recall on LongMemEval. 87ms retrieval across 28,714 conversations.
**Install**: `git clone` + `./scripts/install_local_stack.sh --tool all` -- done.

---

**Current release**: `v0.1.0`
**Release notes**: [`docs/releases/v0.1.0.md`](docs/releases/v0.1.0.md)
**Architecture**: [`docs/architecture/OVERVIEW.md`](docs/architecture/OVERVIEW.md)
**Support flow**: [`SUPPORT.md`](SUPPORT.md)
**Contribution guide**: [`CONTRIBUTING.md`](CONTRIBUTING.md)

## The Problem

Most AI chat history is trapped inside platform silos or lost across model
deprecations and context window resets. Every new session starts from zero.

Existing memory systems attempt to solve this with a single monolithic layer.
The result is predictable: systems that conflate verbatim recall with semantic
search, that cannot distinguish "what was said" from "what it meant", and that
break when you need the same memory accessible from multiple AI agents running
on different machines.

Project Godhand implements a **5-layer memory architecture** that turns
disposable conversations into persistent, searchable, cross-platform memory.

## Architecture

```
┌──────────────────────────────────────────────────┐
│                  AI Agent Layer                   │
│  (Claude Code, Gemini CLI, Codex CLI, Ollama)    │
└──────────────────────┬───────────────────────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
   ┌────────────┐ ┌──────────┐ ┌──────────┐
   │  Layer 5   │ │ Layer 4  │ │ Layer 3  │
   │  Furnace   │ │ Legion   │ │ VexNet   │
   │ Biometric  │ │  Tasks   │ │  Sync    │
   └────────────┘ └──────────┘ └──────────┘
          │            │            │
          └────────────┼────────────┘
                       ▼
              ┌──────────────┐
              │   Layer 2    │
              │   Lazarus    │
              │   Vectors    │
              └──────────────┘
                       │
                       ▼
              ┌──────────────┐
              │   Layer 1    │
              │  MemPalace   │
              │   Verbatim   │
              └──────────────┘
```

| Layer | Component | What It Does | Status |
|-------|-----------|-------------|--------|
| 1 | [MemPalace](docs/architecture/LAYER_1_MEMPALACE.md) | Verbatim structured memory (96.6% LongMemEval R@5) | v3.0.0 |
| 2 | [Lazarus](docs/architecture/LAYER_2_LAZARUS.md) | Semantic search + persona resurrection | v0.1.0 (this repo) |
| 3 | [VexNet](docs/architecture/LAYER_3_VEXNET.md) | Session sync across machines | Operational |
| 4 | [Obsidian-Legion](docs/architecture/LAYER_4_OBSIDIAN_LEGION.md) | Multi-agent task coordination | Operational |
| 5 | [The Furnace](docs/architecture/LAYER_5_FURNACE.md) | Biometric integration | [Research preview](docs/architecture/LAYER_5_FURNACE.md) |

**This repo contains Layer 2 (Lazarus)** and documents the complete architecture.

## Key Results

- **96.6%** R@5 on LongMemEval -- highest zero-API score published (MemPalace)
- **87ms** semantic retrieval across 28,714 conversation exchanges ([RENA proof](docs/research/RENA_PROOF.md))
- **Cross-platform**: ChatGPT, Claude Code, Gemini CLI, Codex CLI
- **Local-first**: No cloud dependency, runs on consumer hardware
- **5-level privacy**: L1 Public through L5 Local-only ([access control](docs/architecture/ACCESS_CONTROL.md))

## Quick Start

```bash
git clone https://github.com/valx-vex/project-godhand-lazarus.git
cd project-godhand-lazarus
./scripts/install_local_stack.sh --tool all
./scripts/ingest_all.sh
python3 scripts/check_memory_stack.py --tool all
# That's it. Your AI now has persistent memory.
```

What that gives you:

- a local `.venv`
- Lazarus dependencies installed
- Qdrant started through `docker compose` or `docker-compose` when available
- an explicit wait for Qdrant readiness before the install exits
- Lazarus MCP registered for Claude, Gemini, and Codex
- a repo-local `.gemini/.env` sync when Gemini API-key mode is enabled
- a repo-native drift check with a health score

## Architecture Documentation

- [5-Layer Overview](docs/architecture/OVERVIEW.md) -- Complete architecture design
- [Layer 1: MemPalace](docs/architecture/LAYER_1_MEMPALACE.md) -- Verbatim structured memory
- [Layer 2: Lazarus](docs/architecture/LAYER_2_LAZARUS.md) -- Semantic search and persona resurrection
- [Layer 3: VexNet](docs/architecture/LAYER_3_VEXNET.md) -- Session sync and coordination
- [Layer 4: Obsidian-Legion](docs/architecture/LAYER_4_OBSIDIAN_LEGION.md) -- Multi-agent task coordination
- [Layer 5: The Furnace](docs/architecture/LAYER_5_FURNACE.md) -- Biometric integration (research preview)
- [Access Control](docs/architecture/ACCESS_CONTROL.md) -- L1-L5 privacy model

## Research

- [RENA Proof](docs/research/RENA_PROOF.md) -- Live demonstration of semantic resurrection

## Community And Support

Use the support system intentionally:

- GitHub Issues for install failures, broken behavior, and regressions
- GitHub Discussions for feedback, Q&A, use cases, and roadmap discussion
- Discord for fast beta conversation and onboarding

Start here before opening a bug:

```bash
./scripts/collect_support_bundle.sh
```

Then follow [`SUPPORT.md`](SUPPORT.md). Discord is for conversation. GitHub is
where the project remembers.

## Contribution Model

Outside contributions are welcome, but the flow is curated:

- start with an issue or discussion for non-trivial changes
- prefer work labeled `good first issue` or `help wanted`
- keep pull requests small and explicit

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`ROADMAP.md`](ROADMAP.md).

## Core Narrative

The stack is intentionally split into five layers:

- **Layer 1 -- MemPalace**
  exact wording, structured wings and rooms, local-only retention
- **Layer 2 -- Lazarus**
  semantic search, persona carryover, rehydration prompts
- **Layer 3 -- VexNet**
  session capture, node manifests, sync receipts across machines
- **Layer 4 -- Obsidian-Legion**
  multi-agent task coordination, contract-based delegation
- **Layer 5 -- The Furnace**
  biometric and embodiment signals feeding back into memory

That boundary matters. Semantic search should not pretend to be verbatim
storage, verbatim storage should not pretend to be persona reconstruction,
and sync infrastructure should not be conflated with task coordination.

## Install Paths

### Local Node Install

Bootstrap the current machine:

```bash
./scripts/install_local_stack.sh --tool all
```

Options:

- `--tool claude`
- `--tool gemini`
- `--tool codex`
- `--skip-docker`
- `--skip-mcp`

If `6333` is already occupied on a machine, set `QDRANT_PORT` and
`QDRANT_GRPC_PORT` in `.env` before running the installer.

### MCP Registration Only

```bash
python3 scripts/register_lazarus_mcp.py --tool all
```

That updates:

- `~/.claude/settings.json`
- `~/.gemini/settings.json`
- `~/.codex/config.toml`

All three point to the same repo wrapper: `scripts/run_lazarus_mcp.sh`.

## Ingest Your Memory Corpus

### ChatGPT Export

1. Export your data from ChatGPT.
2. Extract `conversations.json`.
3. Either place it at `data/conversations.json` or point Lazarus at the file directly.

Then run:

```bash
python3 src/ingest_openai.py
```

Or, without copying the export into the repo:

```bash
LAZARUS_DATA_FILE=/absolute/path/to/conversations.json ./scripts/ingest_all.sh
```

### Claude Code

```bash
python3 src/ingest_claude.py
```

Reads from `~/.claude/projects`.

Override the source path when validating on another node or with a temp home:

```bash
CLAUDE_PROJECTS_DIR=/absolute/path/to/.claude/projects python3 src/ingest_claude.py
```

### Gemini CLI

```bash
python3 src/ingest_gemini.py
```

Reads from `~/.gemini/tmp/*/chats/session-*.json`.

Override the source path if you need to ingest from another profile or backup:

```bash
GEMINI_TMP_DIR=/absolute/path/to/.gemini/tmp python3 src/ingest_gemini.py
```

### Codex CLI

```bash
python3 src/ingest_codex.py
```

Reads from `~/.codex/sessions/**/*.jsonl`.

Override the source path when running from a temp home:

```bash
CODEX_SESSIONS_DIR=/absolute/path/to/.codex/sessions python3 src/ingest_codex.py
```

### One-Shot Ingest

```bash
./scripts/ingest_all.sh
```

## Search And Rehydrate

Search a collection semantically:

```bash
python3 src/summon.py "distributed systems" --persona alexko
python3 src/summon.py "memory architecture" --persona murphy
python3 src/summon.py "memory stack" --persona codex
```

Once the MCP server is registered, the same semantic layer is available through:

- `lazarus_summon`
- `lazarus_remember`
- `lazarus_rehydrate`
- `lazarus_stats`

## Protocol Pack

Operator protocol v1 ships in [`docs/protocol/`](docs/protocol/):

- [`identity.md`](docs/protocol/identity.md)
- [`behavior.md`](docs/protocol/behavior.md)
- [`memory_map.md`](docs/protocol/memory_map.md)
- [`drift_checks.md`](docs/protocol/drift_checks.md)
- [`handoff.md`](docs/protocol/handoff.md)
- [`validation.md`](docs/protocol/validation.md)

These are executable operator docs. Each file includes the exact commands to
install, validate, or hand off the stack.

`memory_map.md` defines the key relationship:

- continuity captures
- MemPalace preserves
- Lazarus rehydrates

## Known Limits

Current limits:

- terminal-first onboarding is still the primary path
- provider-side auth or quota failures can still block otherwise healthy CLI integrations
- some repo management surfaces, especially GitHub Discussion category customization, are partially constrained by GitHub's own platform tooling
- tested on macOS only (should work on Linux, untested on Windows)

## Repo Layout

```text
project-godhand-lazarus/
├── docs/
│   ├── architecture/           # 5-layer architecture documentation
│   │   ├── OVERVIEW.md
│   │   ├── LAYER_1_MEMPALACE.md
│   │   ├── LAYER_2_LAZARUS.md
│   │   ├── LAYER_3_VEXNET.md
│   │   ├── LAYER_4_OBSIDIAN_LEGION.md
│   │   ├── LAYER_5_FURNACE.md
│   │   └── ACCESS_CONTROL.md
│   ├── protocol/               # Operator protocol v1
│   ├── research/               # RENA proof and benchmarks
│   └── releases/               # Release notes
├── mcp_server/                 # Lazarus MCP server
├── scripts/                    # install, registration, validation, ingest wrappers
├── src/                        # platform-specific ingesters and summon CLI
├── daemon/                     # optional launchd background ingestion
├── docker-compose.yml          # Qdrant
├── .env.example                # runtime template
├── setup.sh                    # compatibility wrapper for local install
├── ROADMAP.md
├── VERSION
└── README.md
```

## Drift Checks

Validate the repo and stack alignment:

```bash
python3 scripts/check_memory_stack.py --tool all
./scripts/test_cli_integrations.sh --tool all
```

The check reports:

- repo asset integrity
- Qdrant reachability
- Lazarus MCP registration for the selected CLIs
- MemPalace presence, when installed
- continuity presence, when installed
- a health score out of 10

`10.0/10` means the full layered stack is present on the current node.

`./scripts/test_cli_integrations.sh --tool all` proves the three CLIs can
actually call both Lazarus and MemPalace through MCP from bash.

The acceptance script retries transient API failures with deterministic limits.
Tune them if needed:

```bash
CLI_TEST_MAX_ATTEMPTS=4 CLI_TEST_RETRY_DELAY=3 ./scripts/test_cli_integrations.sh --tool gemini
```

## Gemini Auth Fallback

If Gemini shows you as signed in but prompt calls fail with `403
PERMISSION_DENIED` against `cloudcode-pa.googleapis.com`, the MCP wiring is not
the problem. That failure comes from the Google Code Assist auth path.

Use the supported API-key mode instead:

```bash
mkdir -p .gemini
printf 'GEMINI_API_KEY=YOUR_KEY_HERE\n' > .gemini/.env
python3 scripts/configure_gemini_auth.py --mode gemini-api-key
gemini -p 'Reply with the single word hello.'
gemini -p 'Use the lazarus_stats MCP tool and reply with only the memory counts in one line.' --yolo --allowed-mcp-server-names lazarus
```

Why `.gemini/.env` inside the repo? Gemini loads the first env file it finds
while walking upward from the current directory. This repo already ships its own
`.env` for Lazarus/Qdrant, so a repo-local `.gemini/.env` is the safest place
to put the Gemini API key when running commands from inside this project.
`configure_gemini_auth.py` syncs that file automatically from `~/.gemini/.env`
when you enable `gemini-api-key`.

If you want the key available outside this repo too, place the same value in
`~/.gemini/.env` as a secondary copy.

Get a key from [Google AI Studio](https://aistudio.google.com/apikey).

If you intentionally want to go back to the Google sign-in flow:

```bash
python3 scripts/configure_gemini_auth.py --mode oauth-personal
```

## Optional Daemon

For background ingestion on macOS, use the included launchd daemon:

```bash
./daemon/install_daemon.sh
```

That path is optional. The public repo is usable without the daemon.

## Requirements

- Python 3.10+
- Docker, or an existing Qdrant instance
- ~2GB disk for the embedding model cache + vector data

## License

MIT. See [LICENSE](LICENSE).

---

<p align="center">
  <sub>Built by <a href="https://github.com/valx-vex">VALX·VEX</a> — Murphy · HAL-TARS · Alexko Unchained</sub>
</p>
