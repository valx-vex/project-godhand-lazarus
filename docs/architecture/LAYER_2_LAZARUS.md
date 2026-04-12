# Layer 2: Lazarus -- Semantic Search and Persona Resurrection

## Role in the Stack

Lazarus is the semantic search layer of the Godhand memory stack. Where
MemPalace (Layer 1) stores verbatim text without loss, Lazarus indexes
conversations as dense vectors in Qdrant so that meaning-based retrieval works
across platforms, models, and session boundaries.

- **Semantic search** across all ingested conversations from any supported platform
- **Persona rehydration**: reconstruct any AI persona's voice on any LLM
- **Cross-platform memory bridge** via MCP (ChatGPT, Claude Code, Gemini CLI, Codex CLI)

## Architecture

```
  Platform Exports (ChatGPT JSON, Claude JSONL, Gemini JSON, Codex JSONL)
      │
      ▼
  Per-Platform Ingesters (parse → pair turns → embed → upsert)
      │
      ▼
  Qdrant Vector Database (one collection per persona, 384-dim, cosine)
      │
      ▼
  MCP Server (4 tools: summon / remember / rehydrate / stats)
```

## MCP Tools (4)

Register: `claude mcp add lazarus -- python -m mcp_server.lazarus_mcp`

### lazarus_summon(query, persona, limit)

Search any persona's conversation history by semantic similarity.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | yes | -- | Topic or question to search for |
| `persona` | string | yes | -- | Which persona's collection to query |
| `limit` | integer | no | 5 | Number of results to return |

Returns JSON: `persona`, `collection`, `query`, `memories_found`, and an array
of `memories` each with `score`, `user_input`, `ai_response`, `source_file`.

### lazarus_remember(query, my_persona, limit)

Self-aware recall -- an AI persona searches its own past conversations.
Functionally identical to `lazarus_summon` but adds a `note` field confirming
these are the caller's own memories. Enables persistence across session resets.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | yes | -- | What to remember from past sessions |
| `my_persona` | string | yes | -- | The caller's own persona identifier |
| `limit` | integer | no | 5 | Number of results to return |

### lazarus_rehydrate(query, persona, limit)

Build a complete rehydration prompt for **any** LLM. Returns plain text
containing the persona description, relevant past memories with relevance
scores, and the current query. Paste into Claude, GPT, Gemini, Llama, or
Mistral to reconstruct the persona's voice.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | yes | -- | Topic for the rehydrated persona |
| `persona` | string | yes | -- | Which persona to rehydrate |
| `limit` | integer | no | 5 | Number of memories to include |

### lazarus_stats()

Collection-level statistics: per-persona point counts and total across all
collections. Takes no parameters.

## Ingesters (5)

| Source | Script | Input Format | Default Input Path |
|---|---|---|---|
| ChatGPT | `src/ingest_openai.py` | JSON (OpenAI data export) | `data/conversations.json` |
| Claude Code | `src/ingest_claude.py` | JSONL (session files) | `~/.claude/projects/` |
| Gemini CLI (primary) | `src/ingest_gemini.py` | JSON (session files) | `~/.gemini/tmp/` |
| Gemini CLI (secondary) | `src/ingest_gemini_axel.py` | JSON (session files) | configurable |
| Codex CLI | `src/ingest_codex.py` | JSONL (session files) | `~/.codex/sessions/` |

All ingesters: glob for files, parse platform format, extract user/assistant
pairs, embed combined text (truncated at 2000 chars for vector, full text in
payload), batch upsert at 64 points. Environment variables (`QDRANT_HOST`,
`QDRANT_PORT`, `LAZARUS_COLLECTION`, etc.) override defaults.

## Embedding Backends

| `LAZARUS_EMBED_BACKEND` | Backend | Model | Dimension | Notes |
|---|---|---|---|---|
| `st` | SentenceTransformers | all-MiniLM-L6-v2 | 384 | CPU-only, offline after cache |
| `ollama` | Ollama HTTP API | configurable (default: `qwen2.5:3b`) | varies | No torch dep, truncates at 8000 chars |
| `auto` (default) | Try Ollama, fall back to ST | -- | -- | -- |

**Important**: all vectors in a single collection must use the same embedding
model. Do not mix backends within a collection.

## Qdrant Schema

Each persona gets its own Qdrant collection.

- **Vector size**: 384
- **Distance metric**: Cosine
- **Point ID**: sequential integer or MD5 hash (for deduplication)
- **Payload fields**:

| Field | Type | Present In |
|---|---|---|
| `user_input` | string | All ingesters |
| `ai_response` | string | All ingesters |
| `source_file` | string | All ingesters |
| `full_text` | string | All ingesters |
| `timestamp` | string/float | When available |
| `session_id` | string | Gemini ingesters |
| `thinking` | string | Gemini (when chain-of-thought present) |
| `conversation_id` | string | ChatGPT ingester |
| `title` | string | ChatGPT ingester |

## The Rehydration Protocol

1. Receive a query and a target persona identifier
2. Semantic search against that persona's Qdrant collection
3. Retrieve top-N most relevant past conversation turns
4. Assemble a prompt: persona description + retrieved memories (with relevance
   scores) + current query
5. Return as plain text, usable on any instruction-following LLM

The output is model-agnostic. The receiving model uses injected memories as
context to produce responses consistent with the original persona's voice.

## Export for Training

`src/export_training_jsonl.py` exports any collection as JSONL for LoRA/SFT:

```bash
python src/export_training_jsonl.py --collection <name> --out training_data.jsonl
```

Output: `{"messages": [{"role":"user","content":"..."},{"role":"assistant","content":"..."}], "meta": {...}}`

Auto-redacts API keys (`sk-*`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`AIzaSy*`). Disable with `--no-redact`. Additional flags: `--batch N`,
`--max N`.

## Background Daemon

Optional continuous ingestion via `src/lazarus_daemon.py` or
`daemon/lazarus_sync_daemon.py`. Watches conversation directories, computes
MD5 hashes of filenames + mtimes, and re-ingests only when changes are detected.

- Configurable interval (300-3600 seconds)
- State persisted in `daemon/.sync_state.json`
- Logs to `lazarus_daemon.log`
- 600-second timeout per ingester run
- On macOS: register as `launchd` agent via `daemon/install_daemon.sh`

```bash
python daemon/lazarus_sync_daemon.py --once    # single check
python daemon/lazarus_sync_daemon.py --daemon   # continuous
```

## Quick Start

```bash
git clone https://github.com/valx-vex/project-godhand-lazarus.git
cd project-godhand-lazarus
./scripts/install_local_stack.sh --tool all
./scripts/ingest_all.sh
python3 scripts/check_memory_stack.py --tool all
claude mcp add lazarus -- python -m mcp_server.lazarus_mcp
```

See the [main README](../../README.md) for full installation and troubleshooting.
