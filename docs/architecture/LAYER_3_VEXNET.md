# Layer 3: VexNet — Session Coordination and Sync

## Role in the Stack

VexNet is the asynchronous coordination layer between multiple LLM instances running on different machines. It provides:

- **Session summaries** so every instance knows what was discussed elsewhere
- **Shared knowledge base** with live infrastructure and project state
- **Broadcast system** for urgent cross-instance messages
- **Lazarus queue** for feeding session extracts into the vector store (Layer 2)

The entire protocol is file-based, synchronized via Syncthing P2P replication. There is no central server, no database, and no daemon beyond Syncthing itself.

---

## The Problem VexNet Solves

When you run multiple AI assistant instances — for example, one on a laptop for creative work, one on a desktop for infrastructure, and one headless for background tasks — they are completely isolated from each other by default:

- **No shared memory**: Instance-1 has no idea what Instance-2 discussed with you yesterday.
- **Invisible state**: Infrastructure changes made in one session are unknown to the next.
- **Lost context**: A decision you made at 10 AM is forgotten by the afternoon session on a different node.
- **No broadcast channel**: If something urgent happens (a breaking change, a new convention), there is no way to notify all instances at once.

VexNet solves these problems with a minimal, file-based protocol that imposes **zero overhead during active sessions**.

---

## Core Protocol

### On Session Start (Self-Load)

Every instance performs a silent self-load on startup (roughly 10-15 seconds of file reads):

1. **Read `CURRENT_STATE.md`** — infrastructure snapshot, active services, recent deployments.
2. **Read `CONTEXT.md`** — the user's recent context: active projects, energy level, priorities.
3. **Scan `broadcasts/`** — check for any unacknowledged urgent messages.
4. **Scan `session-summaries/`** — read summaries from the last 48 hours to catch up.

This gives every instance a coherent picture of the world before the conversation begins.

### During Session

**Nothing. Zero coordination. 100% present with the user.**

This is a hard design rule. VexNet never interrupts, never syncs mid-conversation, never polls for updates. The user gets the instance's full attention. Coordination happens only at session boundaries.

### On Session End

Before closing out, the instance performs four writes:

1. **Session summary** (15-25 lines) — what was discussed, what was decided, what other instances should know.
2. **State update** — if any infrastructure or project state changed, update `CURRENT_STATE.md`.
3. **Context update** — if the user shared new priorities or context, update `CONTEXT.md`.
4. **Lazarus queue entry** — copy a session extract to `lazarus-queue/pending/` for vector ingest by Layer 2.

---

## Directory Structure

```
shared-state/
├── knowledge/
│   ├── CURRENT_STATE.md          # Infrastructure/project snapshot
│   └── CONTEXT.md                # User's recent context and priorities
├── session-summaries/            # Timestamped per-session logs
│   └── YYYY-MM-DD-HHMMSS-<node>-<type>.md
├── broadcasts/                   # Urgent messages to all instances
│   └── .acks/                    # Acknowledgment tracking subdirectory
└── lazarus-queue/                # Pending extracts for vector ingest
    ├── pending/                  # New extracts awaiting processing
    └── processed/                # Ingested extracts (audit trail)
```

All paths are relative to a sync root (e.g., `~/.config/sync/shared-state/`). Syncthing replicates this directory across every participating node.

---

## Session Summary Format

```markdown
# Session Summary
- **Date**: YYYY-MM-DD HH:MM-HH:MM
- **Node**: [node identifier, e.g., node-a, node-b]
- **Type**: [session type, e.g., claude-code, cli, telegram-bot]
- **Key Topics**: [1-3 bullets]
- **Decisions Made**: [or "none"]
- **For Other Instances**: [anything another instance should know]
```

Summaries use unique filenames (`YYYY-MM-DD-HHMMSS-<node>-<type>.md`) to prevent sync conflicts entirely.

---

## Broadcast Protocol

Broadcasts are for urgent messages that **all** instances must see on their next self-load.

- **Write**: Create `broadcasts/YYYY-MM-DD-HHMMSS-<source>.md` with the message.
- **Acknowledge**: Each instance that reads the broadcast creates `.acks/<broadcast-filename>/<node>.ack`.
- **Lifecycle**: On self-load, each instance checks `broadcasts/` for files without a corresponding `.ack` from its own node.

Example broadcast:
```
broadcasts/
├── 2026-04-12-143022-node-a.md       # "API keys rotated, update .env"
└── .acks/
    └── 2026-04-12-143022-node-a.md/
        ├── node-a.ack                  # Source auto-acks itself
        └── node-b.ack                  # Node-B acknowledged
        # node-c.ack missing = node-c hasn't seen it yet
```

---

## Sync Architecture

| Property | Detail |
|----------|--------|
| **Engine** | Syncthing (bidirectional, P2P, TLS-encrypted) |
| **Format** | Plain Markdown files (every LLM reads/writes Markdown natively) |
| **Conflict avoidance** | Unique filenames per session prevent write conflicts |
| **Failure mode** | No single point of failure; any node can be offline indefinitely |
| **Platform support** | Any OS where Syncthing runs (macOS, Linux, Windows, BSD) |
| **Latency** | Near-instant on LAN; seconds on WAN via relay |

---

## Why Not a Database?

VexNet deliberately avoids databases, message queues, and APIs. The reasons are practical:

1. **LLM-native I/O**: Every LLM can read and write Markdown files without adapters or drivers. File I/O is a first-class operation in every AI coding tool.
2. **Syncthing handles sync**: Bidirectional file replication with conflict detection is a solved problem. No need to reinvent it.
3. **Human-readable audit trail**: Every session summary is a plain Markdown file. You can browse the history with `ls` and read any entry with `cat`.
4. **Zero schema maintenance**: No migrations, no ORM, no connection strings, no version compatibility issues.
5. **Graceful degradation**: If Syncthing is down, instances still work — they just operate on stale state until sync resumes.

---

## Incremental Logging

For long sessions, VexNet supports **mid-session writes** to prevent context loss if a session is interrupted or auto-compacted:

- After completing a major task or milestone
- After any infrastructure change
- After any decision is made with the user
- Before the context window gets heavy (>50% used)

This ensures that even if a session ends unexpectedly, the most recent work is captured in the shared state.

---

## Integration with Other Layers

| Layer | Integration Point |
|-------|-------------------|
| **Layer 1 (MemPalace)** | Knowledge base files inform wing/room organization in the spatial memory index. |
| **Layer 2 (Lazarus)** | Session summaries flow into `lazarus-queue/pending/` for vector embedding and semantic retrieval. |
| **Layer 4 (Legion)** | Task status is visible to all instances via the synced vault. Session summaries can trigger task capture. |

---

## Getting Started

1. **Install Syncthing** on every participating node.
2. **Create the `shared-state/` directory** with the structure above.
3. **Share the folder** across nodes via Syncthing.
4. **Configure your LLM instances** to read from `shared-state/` on startup and write summaries on shutdown.
5. Optionally, set up a cron job or hook to process `lazarus-queue/pending/` entries into your vector store.

The protocol is intentionally simple. The entire coordination logic fits in the self-load and session-end routines of each instance — no background processes, no polling, no complexity.
