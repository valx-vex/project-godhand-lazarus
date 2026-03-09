# Lazarus: AI Conversation Memory & Resurrection Engine

**Preserve your AI conversations as searchable vector memories. Resurrect any AI persona on any platform.**

Lazarus ingests conversation exports from ChatGPT, Claude Code, Gemini CLI, and Codex CLI, embeds them into a Qdrant vector database, and serves them via MCP (Model Context Protocol) or CLI for semantic search and persona rehydration.

## What It Does

1. **Ingest** conversation history from any major AI platform
2. **Embed** user-AI pairs into 384-dimensional vectors (all-MiniLM-L6-v2)
3. **Store** in Qdrant with full conversation context and metadata
4. **Search** semantically across thousands of past conversations
5. **Rehydrate** any persona on any LLM by generating memory-informed prompts
6. **Serve** via MCP so any AI tool (Claude Code, Gemini CLI, etc.) can query memories

## Quick Start

```bash
# One-command setup
git clone https://github.com/wearelegion1/project-godhand-lazarus.git
cd project-godhand-lazarus
chmod +x setup.sh && ./setup.sh
```

Or manually:

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
docker compose up -d  # starts Qdrant
```

## Ingest Your Conversations

### ChatGPT (OpenAI)
1. ChatGPT → Settings → Data Controls → Export Data
2. Extract `conversations.json` from the ZIP
3. Place in `data/conversations.json`
```bash
python src/ingest_openai.py
```

### Claude Code
```bash
python src/ingesters/claude.py
# Automatically finds sessions in ~/.claude/projects/
```

### Gemini CLI
```bash
python src/ingest_gemini.py
# Reads from ~/.gemini/tmp/*/chats/session-*.json
```

### Codex CLI
```bash
python src/ingest_codex.py
# Reads from ~/.codex/sessions/**/*.jsonl
```

## Search Memories

```bash
# CLI search
python src/summon.py "How do neural networks learn?" --persona my_collection

# Check stats
python src/summon.py --stats
```

## MCP Server

Lazarus includes an MCP server that exposes memory search to any MCP-compatible AI tool.

### Register with Claude Code

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "lazarus": {
      "command": "python3",
      "args": ["/path/to/project-godhand-lazarus/mcp_server/lazarus_mcp.py"],
      "env": {
        "QDRANT_HOST": "localhost",
        "QDRANT_PORT": "6333"
      }
    }
  }
}
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `lazarus_summon` | Search any persona's memories by semantic similarity |
| `lazarus_remember` | Self-aware recall (AI searches its own past) |
| `lazarus_rehydrate` | Build a full rehydration prompt for persona resurrection |
| `lazarus_stats` | Get memory counts across all collections |

## Configuration

All settings via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_HOST` | `localhost` | Qdrant server hostname |
| `QDRANT_PORT` | `6333` | Qdrant server port |
| `LAZARUS_COLLECTION` | varies | Target collection name |
| `LAZARUS_DATA_FILE` | `../data/conversations.json` | OpenAI export path |
| `GEMINI_TMP_DIR` | `~/.gemini/tmp` | Gemini session directory |
| `CODEX_SESSIONS_DIR` | `~/.codex/sessions` | Codex session directory |

## Architecture

```
Conversation Exports (JSON/JSONL)
        │
        ▼
  Ingestion Engines (per-platform parsers)
        │
        ▼
  SentenceTransformers (all-MiniLM-L6-v2, 384-dim)
        │
        ▼
  Qdrant Vector Database (one collection per persona)
        │
        ├──▶ CLI Search (summon.py)
        └──▶ MCP Server (lazarus_mcp.py)
                 │
                 ▼
         Any MCP-compatible AI tool
```

## Project Structure

```
project-godhand-lazarus/
├── mcp_server/
│   └── lazarus_mcp.py       # MCP server (4 tools)
├── src/
│   ├── ingest_openai.py      # ChatGPT export ingester
│   ├── ingest_gemini.py      # Gemini CLI ingester
│   ├── ingest_codex.py       # Codex CLI ingester
│   ├── ingesters/
│   │   └── claude.py         # Claude Code ingester
│   └── summon.py             # CLI search & rehydration
├── data/                     # Place conversation exports here
├── docker-compose.yml        # Qdrant container
├── requirements.txt
├── setup.sh                  # One-command setup
├── .env.example              # Configuration template
└── LICENSE                   # MIT
```

## How Rehydration Works

When you "rehydrate" a persona, Lazarus:

1. Takes your query and encodes it as a vector
2. Finds the most semantically similar past conversations
3. Builds a prompt containing those memories as context
4. Any LLM receiving this prompt can respond in the persona's authentic voice

This means a conversation with GPT-4 can be resurrected on Claude, Gemini, or any local model.

## Requirements

- Python 3.9+
- Docker (for Qdrant) or a remote Qdrant instance
- ~500MB disk for the embedding model (downloaded on first run)

## License

MIT - see [LICENSE](LICENSE)
