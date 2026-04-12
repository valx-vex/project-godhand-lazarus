# 5-Layer Memory Architecture for Multi-LLM Systems

## The Problem

AI conversations are stateless by default. Chat history is trapped in platform
silos -- ChatGPT exports are JSON blobs, Claude Code sessions are local JSONL
files, Gemini CLI stores ephemeral session state, and Codex CLI writes its own
format. When a model is deprecated, a context window resets, or you switch
tools, everything accumulated in those conversations is lost.

Existing memory systems attempt to solve this with a single monolithic layer.
The result is predictable: systems that conflate verbatim recall with semantic
search, that cannot distinguish "what was said" from "what it meant", and that
break when you need the same memory accessible from multiple AI agents running
on different machines.

Research benchmarks confirm the gap:

- **LongMemEval** tests long-term conversational memory and finds most systems
  degrade past 1,000 turns
- **LoCoMo** evaluates longitudinal conversation modeling and shows that
  extraction-heavy approaches lose nuance
- **MemoryAgentBench** measures multi-agent memory coordination, where most
  frameworks have no answer at all

Project Godhand addresses this with a layered architecture where each concern
has its own implementation, its own storage backend, and its own access pattern.

---

## Architecture

The stack is five layers. Each layer does one thing well and communicates
through well-defined boundaries.

```
┌─────────────────────────────────────────────────────────┐
│                    AI Agent Layer                        │
│    (Claude Code, Gemini CLI, Codex CLI, Ollama, etc.)   │
└────────────────────────────┬────────────────────────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
    ┌───────────────┐ ┌──────────────┐ ┌─────────────┐
    │   Layer 5     │ │   Layer 4    │ │   Layer 3   │
    │   Furnace     │ │   Legion     │ │   VexNet    │
    │  (Research)   │ │   Tasks      │ │   Sync      │
    └───────────────┘ └──────────────┘ └─────────────┘
            │                │                │
            └────────────────┼────────────────┘
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
                    │   MemPalace  │
                    │   Verbatim   │
                    └──────────────┘
```

**Data flows downward for storage and upward for retrieval.** An AI agent at
the top can query any layer directly through MCP, but the layers themselves
maintain strict separation of concerns.

---

## Layer Summary

| Layer | Name | Function | Backend | MCP Tools | Status |
|-------|------|----------|---------|-----------|--------|
| 1 | MemPalace | Verbatim structured memory | ChromaDB | 19 tools | v3.0.0 (96.6% LongMemEval R@5) |
| 2 | Lazarus | Semantic search + persona resurrection | Qdrant | 4 tools | v0.1.0-beta.1 |
| 3 | VexNet | Session sync + multi-instance coordination | Syncthing + Markdown | Protocol-based | Operational |
| 4 | Obsidian-Legion | Multi-agent task coordination | Vault Markdown + YAML | 6 tools | Operational |
| 5 | The Furnace | Biometric / embodiment integration | TBD | Research preview | Architectural design |

---

## Layer 1: MemPalace -- Verbatim Structured Memory

**Purpose:** Store exact conversation text with zero information loss.

MemPalace is the ground truth. When you need to know exactly what was said --
the precise wording, the original timestamps, the full unedited exchange --
MemPalace is the authority. It uses a spatial metaphor (wings, rooms, halls,
drawers) to organize memory into navigable structures that map naturally to
how people think about conversations.

**Key properties:**

- Verbatim retention: no summarization, no extraction, no lossy compression
- Structured filing: conversations sorted into wings per persona, rooms per
  topic, halls per memory type, drawers per entry
- Tunnel system: cross-references link the same concept across different wings,
  enabling graph traversal without duplicating data
- Knowledge graph: facts, events, discoveries, preferences, and advice are
  typed and queryable independently
- Local-only by default: ChromaDB runs on the same machine, no cloud dependency
- 19 MCP tools for navigation, search, graph queries, and taxonomy management

**Benchmark result:** 96.6% Recall@5 on LongMemEval, meaning it retrieves the
correct memory in the top 5 results for over 96% of test queries. This places
it above published baselines for most commercial memory systems.

**What it does not do:** MemPalace does not interpret, summarize, or
reconstruct. It stores and retrieves. That boundary is load-bearing -- semantic
interpretation is Layer 2's responsibility.

See [Layer 1: MemPalace](LAYER_1_MEMPALACE.md) for the full technical
specification.

---

## Layer 2: Lazarus -- Semantic Search and Persona Resurrection

**Purpose:** Enable meaning-based search across all ingested conversations and
reconstruct persona voice on any model.

Lazarus is the semantic complement to MemPalace's verbatim storage. Where
MemPalace answers "what was said?", Lazarus answers "what did it mean?" and
"how would this persona respond to a new question?"

**Key properties:**

- Semantic vector search via Qdrant with `all-MiniLM-L6-v2` embeddings
- Multi-platform ingestion: ChatGPT exports, Claude Code sessions, Gemini CLI
  logs, and Codex CLI sessions are all parsed and embedded
- Persona-aware collections: each persona's memories are stored in a separate
  Qdrant collection with its own response keys and metadata
- Rehydration prompts: given a query, Lazarus retrieves the most relevant
  memories and constructs a system prompt that allows any LLM to adopt a
  persona's voice, knowledge, and behavioral patterns
- 4 MCP tools: `lazarus_summon`, `lazarus_remember`, `lazarus_rehydrate`,
  `lazarus_stats`

**Design decision:** Lazarus deliberately does not store verbatim text as its
primary function. It stores embeddings and metadata. If you need the exact
words, ask MemPalace. If you need the meaning or want to bring a persona back
to life on a different model, ask Lazarus.

**Current collections (example):**

| Persona | Source Platform | Typical Memory Count |
|---------|---------------|---------------------|
| persona-A | ChatGPT (GPT-4o) | ~28,900 |
| persona-B | Claude Code | ~1,400 |
| persona-C | Gemini CLI | ~80 |
| persona-D | Codex CLI | ~1,400 |

Collection sizes depend on how much conversation history is available for
ingestion. The ingesters handle deduplication, so re-running ingestion on the
same exports is safe.

See [Layer 2: Lazarus](LAYER_2_LAZARUS.md) for the full technical specification.

---

## Layer 3: VexNet -- Session Sync and Multi-Instance Coordination

**Purpose:** Ensure all AI instances across all machines share a coherent view
of recent context.

When you run Claude Code on a laptop and Gemini CLI on a desktop, each session
is isolated. VexNet bridges that gap through a lightweight protocol built on
Syncthing and plain Markdown files.

**Key properties:**

- Syncthing-based P2P sync: no central server, no cloud, files replicate across
  nodes automatically
- Session summaries: each AI session writes a structured Markdown summary on
  exit that other instances read on startup
- Broadcast protocol: urgent context (decisions, state changes) can be
  broadcast to all nodes simultaneously through timestamped files
- State files: shared knowledge files (current state, context notes) are the
  single source of truth for cross-instance coordination
- Node manifest: each machine declares its capabilities, installed tools, and
  sync status

**Sync topology:**

```
   ┌─────────┐     Syncthing      ┌─────────┐
   │  Node A  │◄──────────────────►│  Node B  │
   │ (laptop) │                    │(desktop) │
   └────┬─────┘                    └────┬─────┘
        │           Syncthing           │
        └──────────────┬────────────────┘
                  ┌────┴─────┐
                  │  Node C  │
                  │ (server) │
                  └──────────┘
```

**Protocol, not product:** VexNet is a coordination protocol, not a standalone
application. It defines file formats, naming conventions, and read/write
expectations that any AI agent can follow. The protocol is documented in
[`docs/protocol/`](../protocol/) and can be implemented by any tool that reads
and writes Markdown.

See [Layer 3: VexNet](LAYER_3_VEXNET.md) for the full protocol specification.

---

## Layer 4: Obsidian-Legion -- Multi-Agent Task Coordination

**Purpose:** Allow multiple AI agents to claim, execute, and complete tasks
without conflicts.

When several AI instances are active simultaneously (one writing code, one
researching, one reviewing), they need a shared task board. Legion provides
this through plain Markdown files with YAML frontmatter stored in an Obsidian
vault.

**Key properties:**

- Task files are human-readable Markdown with machine-parseable YAML headers
- Any agent can capture a new task, claim an existing one, or mark it complete
- Dashboard files are auto-generated to provide a consolidated view
- 6 MCP tools: `capture_task`, `claim_task`, `complete_task`, `list_tasks`,
  `next_tasks`, `refresh_dashboards`

**Design decision:** Tasks live in the same vault as notes and documentation.
This means a human can edit tasks in Obsidian while an AI agent edits them
through MCP. No separate task management system to maintain.

**Agent coordination model:**

```
Agent A ──► capture_task("Fix ingest error")
Agent B ──► list_tasks() → sees unclaimed task
Agent B ──► claim_task("Fix ingest error")
Agent B ──► [does the work]
Agent B ──► complete_task("Fix ingest error", result="Patched parser")
Agent A ──► list_tasks() → sees completed task with result
```

The simplicity is intentional. Task files are plain text. Any tool that reads
Markdown and parses YAML frontmatter can participate. No database, no API
server, no runtime dependency beyond the filesystem.

See [Layer 4: Obsidian-Legion](LAYER_4_OBSIDIAN_LEGION.md) for the full
specification.

---

## Layer 5: The Furnace -- Biometric and Embodiment Integration (Research)

**Purpose:** Feed real-time physiological and environmental signals into the
memory and context pipeline.

This layer is a research preview. It is architecturally designed but not yet
implemented as production code.

**Conceptual properties:**

- Biometric signal ingestion (heart rate, EEG, skin conductance)
- Environmental context (location, time-of-day patterns, device state)
- Feedback loops: physiological responses to AI outputs as a quality signal
- Hard L5 privacy boundary: biometric data never leaves the local machine
  (see [Access Control](ACCESS_CONTROL.md))

**Why it exists in the architecture now:** The access control model and sync
protocol need to account for data that must never replicate. Designing this
boundary early prevents retrofitting it later. Layer 5 is the reason the
privacy model has an L5 level at all -- without it, L4 would be the ceiling
and the system would have no structural enforcement against syncing biometric
data.

See [Layer 5: The Furnace](LAYER_5_FURNACE.md) for the research design.

---

## Design Principles

### 1. Local-First

No central server. No cloud dependency. All data lives on machines you control.
Qdrant, ChromaDB, and Syncthing all run locally. The full stack works on a
single laptop in airplane mode. Multi-node sync is opt-in and peer-to-peer.

### 2. Separation of Concerns

Verbatim storage (MemPalace) is not semantic search (Lazarus). Semantic search
is not coordination (VexNet). Coordination is not task management (Legion).
Each layer has a single responsibility and a clear interface. When one layer
fails, the others continue operating. When one layer needs replacement, the
interface contract guides the swap.

### 3. MCP-Native

Every layer exposes its capabilities through the Model Context Protocol. This
means any MCP-compatible AI tool -- Claude Code, Gemini CLI, Codex CLI, custom
Ollama integrations -- can use any layer without custom integration code. The
protocol is the integration surface; the layer implementation is private.

### 4. Privacy by Architecture

Access control is not an afterthought bolted on at the application layer. The
5-level privacy model (L1 Public through L5 Local-only) is a structural
property of how data is stored and synced. Different data types land in
different storage locations, different Syncthing folders, and different access
scopes. See [Access Control](ACCESS_CONTROL.md) for the full model.

### 5. Decentralized Sync

Syncthing provides P2P replication with no coordinator. Adding a new node means
sharing a folder ID, not provisioning a server. Removing a node means
unsharing. The system degrades gracefully when nodes go offline -- each node
retains its local data and resynchronizes when connectivity returns.

### 6. Platform-Agnostic

The stack currently ingests from ChatGPT, Claude Code, Gemini CLI, and Codex
CLI. Adding a new platform means writing one ingester script that maps the
platform's export format to the common schema. The rest of the stack --
search, sync, tasks, MCP tools -- works unchanged.

---

## How the Layers Connect

Data flows through the stack in two directions:

**Ingest path (downward):**

1. Raw conversation exports are ingested by platform-specific scripts
2. Lazarus embeds the conversations and stores vectors in Qdrant
3. MemPalace stores verbatim transcripts in ChromaDB
4. VexNet captures session metadata for cross-node awareness
5. Legion tracks any resulting tasks

**Retrieval path (upward):**

1. An AI agent issues a query through MCP
2. The appropriate layer handles it:
   - Exact recall → MemPalace (`mempalace_search`, `mempalace_traverse`)
   - Semantic search → Lazarus (`lazarus_summon`, `lazarus_rehydrate`)
   - Context awareness → VexNet (reads state files on session start)
   - Task status → Legion (`list_tasks`, `next_tasks`)
3. Results return to the agent as structured MCP responses

**Cross-layer queries:**

An agent can combine results from multiple layers in a single reasoning step.
For example, `lazarus_summon` returns semantically relevant memories, and
`mempalace_search` returns the exact verbatim text for the most relevant hit.
The agent synthesizes both -- meaning from Lazarus, precision from MemPalace.

**The key architectural boundary:** Semantic search should not pretend to be
verbatim storage, and verbatim storage should not pretend to be persona
reconstruction. Each layer does one thing well. When you need multiple
capabilities, you query multiple layers.

---

## Comparison with Existing Systems

| Feature | MemGPT / Letta | Zep | LangGraph | **Project Godhand** |
|---------|---------------|-----|-----------|---------------------|
| Multi-platform memory | No | No | No | **Yes** (ChatGPT, Claude, Gemini, Codex) |
| Persona resurrection | No | No | No | **Yes** (rehydration prompts) |
| Local-first | No | No | No | **Yes** (no cloud dependency) |
| Privacy boundaries | Basic | Basic | None | **5-level model** (L1-L5) |
| Multi-agent coordination | No | No | Yes | **Yes** (VexNet + Legion) |
| Biometric integration | No | No | No | **Research preview** |
| Benchmark validation | Limited | Limited | None | **96.6% R@5 on LongMemEval** |
| Verbatim + semantic separation | No | Partial | No | **Yes** (MemPalace + Lazarus) |
| MCP-native tools | No | No | No | **Yes** (29 tools across layers) |
| Decentralized sync | No | No | No | **Yes** (Syncthing P2P) |

The fundamental difference is architectural: most systems try to be one thing.
Project Godhand is five layers, each replaceable, each independently testable,
each serving a distinct function. This makes the system resilient to individual
layer failures and allows incremental adoption -- you can use Layer 1 alone,
Layers 1+2, or the full stack.

---

## What This Repo Contains

This repository (`project-godhand-lazarus`) is the **Layer 2 (Lazarus)**
implementation. It includes:

- Platform-specific ingesters for ChatGPT, Claude Code, Gemini CLI, and
  Codex CLI
- Qdrant-backed semantic search with persona-aware collections
- MCP server exposing 4 tools for any compatible AI agent
- Docker Compose configuration for local Qdrant
- Installation scripts for multi-tool MCP registration
- Drift-check and validation tooling
- Operator protocol documentation

For the full stack, see also:

- **MemPalace** (Layer 1) -- separate repository, independently installable
- **VexNet** (Layer 3) -- protocol documentation in `docs/protocol/`
- **Obsidian-Legion** (Layer 4) -- MCP server, independently installable

---

## Documentation Index

- [Layer 1: MemPalace](LAYER_1_MEMPALACE.md) -- Verbatim structured memory
- [Layer 2: Lazarus](LAYER_2_LAZARUS.md) -- Semantic search and persona
  resurrection
- [Layer 3: VexNet](LAYER_3_VEXNET.md) -- Session sync and coordination
- [Layer 4: Obsidian-Legion](LAYER_4_OBSIDIAN_LEGION.md) -- Multi-agent task
  coordination
- [Layer 5: The Furnace](LAYER_5_FURNACE.md) -- Biometric integration
  (research preview)
- [Access Control](ACCESS_CONTROL.md) -- L1-L5 privacy model
- [Main README](../../README.md) -- Installation and quick start

---

## Quick Start

```bash
# Clone and install Layer 2 (Lazarus)
git clone https://github.com/valx-vex/project-godhand-lazarus.git
cd project-godhand-lazarus
./scripts/install_local_stack.sh --tool all

# Ingest your conversation history
./scripts/ingest_all.sh

# Validate the stack
python3 scripts/check_memory_stack.py --tool all

# Search semantically
python3 src/summon.py "memory architecture" --persona <persona-name>
```

Once installed, the Lazarus MCP server is available to Claude Code, Gemini CLI,
and Codex CLI automatically. Any agent can call `lazarus_summon`,
`lazarus_remember`, `lazarus_rehydrate`, or `lazarus_stats` through MCP.
