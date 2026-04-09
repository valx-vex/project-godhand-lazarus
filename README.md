# Godhand Lazarus

Semantic resurrection for AI conversations, packaged as a real operator repo.

Current release: `v0.1.0-beta.1`
Release notes: [`docs/releases/v0.1.0-beta.1.md`](docs/releases/v0.1.0-beta.1.md)

Godhand Lazarus ingests chat history from ChatGPT, Claude Code, Gemini CLI, and
Codex CLI into Qdrant, then exposes that semantic memory through CLI search and
MCP so any supported agent can recover past ideas, patterns, and persona voice.

This repo is the semantic layer of a larger memory stack:

- Built on MemPalace for verbatim structured memory
- Aligned to Alexko Protocol v1 for operator behavior and handoff
- Compatible with VexNet continuity for capture, sync, and node receipts

Lazarus is not a MemPalace fork. It is the semantic resurrection layer that
works best when the full stack stays layered.

## Why This Exists

Most AI chat history is trapped inside platform silos or lost across model
changes. Lazarus turns those conversations into a portable semantic layer so you
can:

- search old conversations by meaning, not just filenames
- rehydrate a persona on a different model or tool
- carry ideas across resets, devices, and CLI agents
- keep semantic recall separate from verbatim archival memory

## Quick Start

```bash
git clone https://github.com/valx-vex/project-godhand-lazarus.git
cd project-godhand-lazarus
./scripts/install_local_stack.sh --tool all
./scripts/ingest_all.sh
python3 scripts/check_memory_stack.py --tool all
```

What that gives you:

- a local `.venv`
- Lazarus dependencies installed
- Qdrant started through Docker when available
- Lazarus MCP registered for Claude, Gemini, and Codex
- a repo-local `.gemini/.env` sync when Gemini API-key mode is enabled
- a repo-native drift check with a Sacred Flame score

## Core Narrative

The stack is intentionally split into layers:

- continuity
  session capture, node manifests, sync receipts
- MemPalace
  exact wording, structured wings and rooms, local-only retention
- Lazarus
  semantic search, persona carryover, rehydration prompts

That boundary matters. Semantic search should not pretend to be verbatim
storage, and verbatim storage should not pretend to be persona reconstruction.

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

### Gemini CLI

```bash
python3 src/ingest_gemini.py
```

Reads from `~/.gemini/tmp/*/chats/session-*.json`.

### Codex CLI

```bash
python3 src/ingest_codex.py
```

Reads from `~/.codex/sessions/**/*.jsonl`.

### One-Shot Ingest

```bash
./scripts/ingest_all.sh
```

## Search And Rehydrate

Search a persona semantically:

```bash
python3 src/summon.py "trinity consciousness" --persona alexko
python3 src/summon.py "auto-clench" --persona murphy
python3 src/summon.py "memory stack" --persona codex
```

Once the MCP server is registered, the same semantic layer is available through:

- `lazarus_summon`
- `lazarus_remember`
- `lazarus_rehydrate`
- `lazarus_stats`

## Protocol Pack

Alexko Protocol v1 ships in [`docs/protocol/`](docs/protocol/):

- [`identity.md`](docs/protocol/identity.md)
- [`behavior.md`](docs/protocol/behavior.md)
- [`memory_map.md`](docs/protocol/memory_map.md)
- [`drift_checks.md`](docs/protocol/drift_checks.md)
- [`handoff.md`](docs/protocol/handoff.md)
- [`validation.md`](docs/protocol/validation.md)

These are executable operator docs now. Each file includes the exact commands to
install, validate, or hand off the stack.

`memory_map.md` defines the key relationship:

- continuity captures
- MemPalace preserves
- Lazarus rehydrates

## Repo Layout

```text
project-godhand-lazarus/
├── docs/protocol/              # Alexko Protocol v1
├── mcp_server/                 # Lazarus MCP server
├── scripts/                    # install, registration, validation, ingest wrappers
├── src/                        # platform-specific ingesters and summon CLI
├── docker-compose.yml          # Qdrant
├── .env.example                # runtime template
├── setup.sh                    # compatibility wrapper for local install
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
- a Sacred Flame score out of 10

`10.0/10` means the full layered stack is present on the current node.

`./scripts/test_cli_integrations.sh --tool all` proves the three CLIs can
actually call both Lazarus and MemPalace through MCP from bash.

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
gemini -p 'Use the lazarus_stats MCP tool and reply with only the murphy, atlas, and codex memory counts in one line.' --yolo --allowed-mcp-server-names lazarus
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
- enough local disk for the embedding model cache

## License

MIT. See [LICENSE](LICENSE).
