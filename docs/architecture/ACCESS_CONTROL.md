# Access Control: The L1-L5 Privacy Model

## Overview

The memory stack handles data with fundamentally different sensitivity levels:
public documentation, shared operational context, private conversation history,
and biometric signals. A flat permission model cannot express these distinctions.

The L1-L5 model is a hybrid of two established access control paradigms:

- **ReBAC (Relationship-Based Access Control):** Access decisions are based on
  the relationship between the requesting entity and the data, not just static
  roles. An AI agent running on the same machine as the data has a different
  relationship than an agent running on a synced remote node.

- **MLS (Multi-Level Security):** Data is classified into ordered levels. Higher
  levels are strictly more restricted. Information flows upward (from less
  restricted to more restricted) freely, but downward flow requires explicit
  declassification.

The combination means: data has a level, and access depends on both the level
and the relationship between requester and data location.

---

## Access Levels

| Level | Name | Visibility | Sync Scope | Example Data |
|-------|------|-----------|------------|-------------|
| **L1** | Public | Anyone | Git repository, public web | README, architecture docs, LICENSE, source code |
| **L2** | Community | Authenticated users | Shared repos, Discussions | Beta feedback, issue reports, redacted support bundles |
| **L3** | Operational | All nodes owned by operator | Syncthing folders, cross-node sync | Session summaries, task boards, shared state files, broadcast messages |
| **L4** | Private | Single operator, all their nodes | Syncthing with restricted folder set | Conversation transcripts, persona collections, personal notes, API keys |
| **L5** | Local-only | Single machine, no replication | Never synced, never backed up off-device | Biometric data, EEG recordings, physiological signals, hardware tokens |

---

## Layer-to-Level Mapping

Each architectural layer has a default access level. Individual data items
within a layer may be elevated (made more restricted) but should not be
lowered below the layer default without explicit justification.

| Layer | Default Level | Sync Behavior | Rationale |
|-------|--------------|---------------|-----------|
| Layer 1: MemPalace | **L4 Private** | Syncs across operator's nodes only | Verbatim transcripts contain personal conversation history |
| Layer 2: Lazarus | **L4 Private** | Syncs across operator's nodes only | Embeddings encode semantic content of private conversations |
| Layer 3: VexNet | **L3 Operational** | Syncs across all operator nodes | Session metadata enables coordination but is not conversation content |
| Layer 4: Legion | **L3 Operational** | Syncs across all operator nodes | Task descriptions are operational, not private conversation data |
| Layer 5: Furnace | **L5 Local-only** | Never syncs | Biometric data has a hard local boundary by design |

**Public layer (L1):** The codebase itself -- source code, documentation,
configuration templates -- is L1. It lives in a public Git repository.

**Community layer (L2):** Support bundles, redacted logs, and community
discussion content. Visible to project participants but not the general public.

---

## Enforcement Points

Access control is enforced at multiple points in the stack:

### 1. Storage Isolation

Each level maps to a different storage location:

```
L1  →  Git repository (public)
L2  →  GitHub Issues/Discussions (authenticated)
L3  →  ~/your-vault/agent-state/shared/    (Syncthing: all nodes)
L4  →  ~/your-vault/agent-state/private/   (Syncthing: restricted set)
L4  →  ~/.mempalace/palace/                (Syncthing: restricted set)
L4  →  Qdrant collections                  (local Docker, synced via backup)
L5  →  ~/your-vault/local-only/            (no Syncthing folder, no backup)
```

### 2. Syncthing Folder Configuration

Sync scope is controlled at the Syncthing folder level, not the file level.
Each access level maps to a separate Syncthing shared folder (or no folder
for L5). This prevents accidental propagation -- a file placed in an L3
folder syncs to all nodes; a file placed in an L5 directory syncs nowhere.

### 3. Git Boundaries

`.gitignore` enforces the L1 boundary. Data directories, environment files,
vector databases, and anything above L1 are excluded from the repository:

```gitignore
data/
*.db
.env
.env.*
qdrant_data/
venv/
```

### 4. MCP Collection Separation

Lazarus stores each persona in a separate Qdrant collection. This enables
per-persona access decisions in future iterations (e.g., sharing one persona's
public outputs while keeping another's private).

---

## Design Principles

### Local-first by default

All data starts at L4 (Private) or higher. Lowering the access level to L3
or below requires explicit action -- sharing a Syncthing folder, committing
to Git, or posting to a community channel. The default is private.

### Sync is opt-in

No data replicates to another machine unless the operator has explicitly
configured a Syncthing folder for it. There is no "sync everything" mode.
Each folder is a conscious decision about what crosses machine boundaries.

### Biometric data has a hard boundary

L5 is not a policy preference. It is a hard architectural constraint. No
Syncthing folder is created for L5 data. No backup script includes it. No
MCP tool exposes it to remote queries. The Furnace layer (Layer 5) operates
exclusively on local data that never leaves the physical device.

### Levels are monotonically ordered

L1 < L2 < L3 < L4 < L5 in terms of restriction. Data can be elevated (an
L3 item can be reclassified as L4) but should not be lowered without review.
This prevents accidental exposure from casual reclassification.

---

## Threat Model

### Threat 1: Sensitive content committed to public repository

**Vector:** A developer accidentally commits conversation data, API keys, or
personal notes to the Git repository.

**Mitigation:**
- `.gitignore` excludes `data/`, `.env`, database files, and virtual
  environments
- Pre-commit review encouraged in `CONTRIBUTING.md`
- Support bundle script (`collect_support_bundle.sh`) redacts secrets before
  output
- Repo ships `.env.example` (template) not `.env` (live secrets)

**Residual risk:** Human error. A determined contributor could force-add an
ignored file. Code review is the final gate.

### Threat 2: Sync propagating private data to unintended nodes

**Vector:** A Syncthing misconfiguration causes L4 data to replicate to a
shared or semi-public node.

**Mitigation:**
- L4 and L5 data live in separate Syncthing folders from L3 data
- Folder sharing is explicit per-device in Syncthing configuration
- `.stignore` files exclude transient and non-essential files from sync
- Node manifests document which folders each machine should have

**Residual risk:** Syncthing trusts its folder configuration. If an operator
adds a device to an L4 folder by mistake, that device receives L4 data.
Operator discipline is required.

### Threat 3: LLM context leaking private data

**Vector:** An AI agent queries Lazarus for private memories and then includes
those memories in output that reaches a less restricted context (e.g., a
public commit message, a shared document).

**Mitigation:**
- Lazarus MCP responses are returned as tool results, not injected into
  system prompts automatically
- Persona collections are separated in Qdrant, enabling future per-collection
  access policies
- The agent layer (Claude Code, Gemini, etc.) controls what it does with
  retrieved memories -- the stack provides data, the agent decides disclosure

**Residual risk:** This is fundamentally an AI agent behavior problem, not a
storage problem. The stack can restrict what data is queryable, but cannot
control what an agent does with query results. Future work may add output
classification hints.

### Threat 4: Biometric data exfiltration

**Vector:** Physiological data (EEG, heart rate, skin conductance) is
captured by a local sensor and could be exfiltrated through sync, backup,
or MCP query.

**Mitigation:**
- L5 is a hard boundary: no Syncthing folder, no backup inclusion, no
  remote MCP access
- Furnace layer (Layer 5) processes biometric data in-memory on the local
  machine only
- Derived signals (e.g., "user attention level: high") may be promoted to
  L4 or L3 after explicit review, but raw biometric data stays L5

**Residual risk:** A compromised local machine has full access to L5 data.
Device-level security (disk encryption, screen lock, OS hardening) is the
defense here, not application-level access control.

---

## Implementation Status

**Honesty note:** The L1-L5 model described here is an architectural
intention, not a runtime ACL enforcement system.

**What is implemented today:**

- **L1 boundary (Git):** `.gitignore` enforced, repository contains only code
  and documentation
- **L3/L4 boundary (Syncthing):** Separate Syncthing folders for operational
  vs. private data, configured per-node
- **L5 boundary (Furnace):** No sync folder exists, no MCP tools expose
  biometric data (Layer 5 is design-only)
- **Collection separation (Lazarus):** Each persona has its own Qdrant
  collection

**What is not yet implemented:**

- Runtime access level tags on individual data items
- Per-query access level enforcement in MCP tools
- Automatic classification of ingested data by sensitivity
- Output classification hints for AI agents
- Audit logging of cross-level data access

The current enforcement is structural (where data is stored determines its
access level) rather than dynamic (no runtime policy engine checks access
on each query). This is sufficient for single-operator use but would need
hardening for multi-operator or shared-infrastructure deployments.

---

## Future Work

- **Per-collection MCP policies:** Allow Lazarus MCP tools to accept an
  access level parameter and filter results accordingly
- **Output tagging:** Mark MCP responses with the access level of their
  source data so agents can make informed disclosure decisions
- **Audit log:** Record which agent queried which collection at what time
- **Multi-operator support:** Extend the model to support shared
  infrastructure where different operators have different access to
  different collections
