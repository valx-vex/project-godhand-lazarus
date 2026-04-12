# Layer 1: MemPalace -- Verbatim Structured Memory

## Role in the Stack

MemPalace is the foundation layer of the Godhand Lazarus memory stack. It stores
actual conversation text **without summarization or extraction**, preserving raw
fidelity so that every decision, debugging session, and architecture debate
survives across sessions.

The spatial metaphor is literal:

- **Wings** represent projects or people
- **Rooms** represent topics within a wing
- **Halls** represent memory types (facts, events, discoveries, preferences, advice)
- **Drawers** hold the original verbatim content
- **Tunnels** cross-reference the same topic across different wings

Everything above this layer -- semantic search, persona rehydration, training
export -- depends on MemPalace's raw fidelity as ground truth.

Lazarus is **not** a MemPalace fork. It is a separate semantic layer that reads
from and complements MemPalace. The two layers stay decoupled so each can evolve
independently.

## Installation

```bash
pip install mempalace
```

- **Version**: 3.0.0
- **License**: MIT
- **Python**: 3.9+
- **Backend**: ChromaDB (local, embedded)
- **External APIs**: None required. Runs entirely on-device.
- **Dependencies**: `chromadb>=0.4.0`, `pyyaml>=6.0`

```bash
# One-time setup
mempalace init ~/projects/myapp

# Mine project files
mempalace mine ~/projects/myapp

# Mine conversation exports (Claude, ChatGPT, Slack, etc.)
mempalace mine ~/chats/ --mode convos

# Search across all stored memories
mempalace search "why did we switch to GraphQL"
```

## Key Capabilities

| Capability | Detail |
|---|---|
| Verbatim storage | Zero information loss -- no summarization, no LLM deciding what to keep |
| LongMemEval R@5 | 96.6% in raw mode (highest published zero-API score) |
| MCP tools | 19 tools across 5 categories |
| AAAK dialect | Experimental lossy abbreviation for high-volume context compression |
| Knowledge graph | SQLite-based temporal entity tracking with validity windows |
| Memory stack | 4 layers: L0 Identity (~50 tokens) through L3 Deep Search (on demand) |
| Local only | No cloud, no subscription, no data leaves the machine |

## The 4-Layer Memory Stack

| Layer | Purpose | Size | Loaded |
|---|---|---|---|
| **L0** | Identity -- who is this AI? | ~50 tokens | Always |
| **L1** | Critical facts -- team, projects, preferences | ~120 tokens | Always |
| **L2** | Room recall -- recent sessions, current project | Variable | On demand |
| **L3** | Deep search -- semantic query across all drawers | Variable | On demand |

The AI wakes up with L0 + L1 (~170 tokens) and has full context awareness.
Deeper searches fire only when needed, keeping per-turn token cost minimal.

## MCP Tools (19)

Register once:

```bash
claude mcp add mempalace -- python -m mempalace.mcp_server
```

### Palace Navigation (7 tools)

| Tool | Description |
|---|---|
| `mempalace_status` | Palace overview, AAAK spec, and memory protocol |
| `mempalace_list_wings` | List all wings with drawer counts |
| `mempalace_list_rooms` | List rooms within a specific wing |
| `mempalace_get_taxonomy` | Full wing-to-room-to-count tree |
| `mempalace_search` | Semantic search with optional wing/room filters |
| `mempalace_check_duplicate` | Check for duplicates before filing new content |
| `mempalace_get_aaak_spec` | Retrieve the AAAK dialect reference |

### Storage (2 tools)

| Tool | Description |
|---|---|
| `mempalace_add_drawer` | File verbatim content into a specific wing/room/hall |
| `mempalace_delete_drawer` | Remove a drawer by ID |

### Knowledge Graph (5 tools)

| Tool | Description |
|---|---|
| `mempalace_kg_add` | Add entity-relationship facts with temporal validity |
| `mempalace_kg_query` | Query entity relationships with optional time filtering |
| `mempalace_kg_invalidate` | Mark a fact as ended without deleting it |
| `mempalace_kg_timeline` | Chronological story of an entity across all facts |
| `mempalace_kg_stats` | Graph overview: entity and triple counts |

### Navigation Graph (3 tools)

| Tool | Description |
|---|---|
| `mempalace_traverse` | Walk the graph from a room across wings |
| `mempalace_find_tunnels` | Find rooms that bridge two different wings |
| `mempalace_graph_stats` | Graph connectivity overview |

### Agent Diary (2 tools)

| Tool | Description |
|---|---|
| `mempalace_diary_write` | Write an AAAK-encoded diary entry for a specialist agent |
| `mempalace_diary_read` | Read recent diary entries for a specialist agent |

## ChromaDB Storage Schema

- **Collection name**: `mempalace_drawers`
- **Vector dimension**: 384 (ONNX MiniLM-L6-v2, runs on CPU)
- **Drawer ID format**: `drawer_{wing}_{room}_{hash}`
- **Metadata fields**: `wing`, `room`, `hall`, `source_file`, `chunk_index`, `added_by`, `filed_at`, `type`

Embedding and storage happen locally. No vectors leave the machine.

## Knowledge Graph

The knowledge graph is a SQLite-based temporal entity-relationship store. It
tracks entities and triples with `valid_from` / `valid_to` windows so that
historical queries return what was true at a specific point in time.

```python
from mempalace.knowledge_graph import KnowledgeGraph

kg = KnowledgeGraph()
kg.add_triple("service-A", "depends_on", "Postgres", valid_from="2025-06-01")
kg.invalidate("service-A", "depends_on", "Postgres", ended="2026-03-01")

# Current state
kg.query_entity("service-A")  # returns only active triples

# Historical state
kg.query_entity("service-A", as_of="2025-12-01")  # returns Postgres dependency
```

Compared to graph databases like Neo4j (used by Zep/Graphiti), the SQLite
backend is local, free, and requires no infrastructure.

## Benchmark Results

| Benchmark | Mode | Score | API Calls |
|---|---|---|---|
| **LongMemEval R@5** | Raw (ChromaDB only) | **96.6%** | Zero |
| **LongMemEval R@5** | Hybrid + Haiku rerank | **100%** (500/500) | ~500 |
| **ConvoMem (Salesforce)** | Raw | **92.9%** | Zero |
| **LoCoMo R@10** | With rerank | **100%** | Reranker only |
| **Palace structure impact** | Wing + room filtering vs unfiltered | **+34%** R@10 | Zero |

The 96.6% raw score is the highest published LongMemEval result that requires no
API key, no cloud dependency, and no LLM at any stage. The 100% hybrid score
uses an optional reranker pass.

**Note (April 2026):** The AAAK compression dialect currently regresses
LongMemEval to 84.2% vs raw mode's 96.6%. AAAK is experimental and is not the
default storage format. Track progress in the upstream repository.

## Integration with Lazarus

MemPalace and Lazarus occupy distinct layers in the stack:

| Concern | MemPalace (Layer 1) | Lazarus (Layer 2) |
|---|---|---|
| Storage | Verbatim text in ChromaDB | Semantic vectors in Qdrant |
| Retrieval | Spatial navigation + semantic search | Cosine similarity search |
| Identity | Palace structure (wings/rooms/halls) | Per-persona collections |
| Purpose | Never lose a word | Find meaning across personas |

Integration touchpoints:

- `check_memory_stack.py` validates both layers and reports a combined health score
- `test_cli_integrations.sh` proves MCP calls work across both MemPalace and Lazarus
- Combined health score: 10.0/10 when the full stack is present and operational
- Each layer can run independently -- MemPalace without Lazarus for archival, Lazarus without MemPalace for semantic search

## AAAK Compression (Experimental)

AAAK is a lossy abbreviation dialect designed for repeated entities at scale. It
uses entity codes, structural markers, and sentence truncation to reduce token
volume when loading large context windows.

**Current status:**

- Lossy, not lossless -- regex-based abbreviation, not reversible compression
- Does not save tokens at small scales (overhead exceeds savings on short text)
- Saves tokens at scale when the same entities appear across thousands of sessions
- Readable by any LLM that reads text -- no special decoder required
- Not the storage default -- raw verbatim is the default and the benchmark winner

## Links

- **PyPI**: <https://pypi.org/project/mempalace/>
- **Repository**: <https://github.com/milla-jovovich/mempalace>
- **Benchmarks**: See `benchmarks/BENCHMARKS.md` in the upstream repository
