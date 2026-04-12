# Layer 4: Obsidian-Legion — Multi-Agent Task Coordination

## Role in the Stack

Legion is a vault-native task engine where **Markdown is the source of truth**, not a plugin database. It provides:

- **One task contract** that every agent understands — human, Claude Code, Codex, Gemini CLI, Ollama, or any future model.
- **Plain-file storage** — tasks are Markdown files with YAML frontmatter, stored in date-partitioned directories.
- **CLI and MCP interfaces** — 9 CLI verbs and 6 MCP tools for programmatic access.
- **No plugin dependency** — works without the Obsidian application running.

---

## The Problem Legion Solves

Multiple AI agents can help build software, write content, and manage infrastructure. But without a shared task contract, they generate **coordination sludge**:

- Agent A finishes a task, but Agent B doesn't know it's done.
- The human assigns work verbally, but there is no persistent record of what was assigned to whom.
- Task state lives in chat history, which is ephemeral and unsearchable.
- Different agents use different formats, making cross-agent handoffs brittle.

Legion eliminates this by giving every agent the **same verbs** against the **same vault data**. A task claimed by one agent is visible to all others. A task completed by Codex is immediately available for the human to review.

---

## Architecture

### Storage

Tasks are plain Markdown files stored in a date-partitioned directory structure:

```
<vault>/tasks/
├── 2026/
│   ├── 03/
│   │   ├── TASK-20260315-001.md
│   │   └── TASK-20260315-002.md
│   └── 04/
│       ├── TASK-20260401-001.md
│       └── TASK-20260412-001.md
└── dashboards/
    ├── active.md          # Auto-generated: all non-terminal tasks
    ├── by-assignee.md     # Auto-generated: grouped by agent
    └── by-project.md      # Auto-generated: grouped by project tag
```

This structure is git-friendly (small diffs, clean history), Syncthing-friendly (unique filenames), and human-browsable (just open the folder).

### Dashboards

Dashboard files are **auto-rendered** from task state by the `refresh` verb. They are read-only views — never edit them directly.

---

## Task Contract (YAML Frontmatter)

Every task file has a standardized YAML frontmatter block:

```yaml
---
task_id: TASK-20260412-001
status: inbox | ready | in_progress | waiting | blocked | done | cancelled
priority: P0 | P1 | P2 | P3
assignee: human | codex | claude-code | gemini-cli | ollama
project: project-name
area: area-tag
summary: "Plain language mission statement"
acceptance:
  - "Done criterion 1"
  - "Done criterion 2"
log:
  - "2026-04-12 14:30: Created from session summary"
  - "2026-04-12 15:00: Claimed by codex"
  - "2026-04-12 16:45: Completed — PR #42 merged"
---

## Notes

Free-form Markdown body for context, links, code snippets, or discussion.
```

### Status Lifecycle

```
inbox → ready → in_progress → done
                     ↓
                  waiting / blocked
                     ↓
               in_progress → done / cancelled
```

### Priority Levels

| Level | Meaning |
|-------|---------|
| **P0** | Drop everything. Do this now. |
| **P1** | Do this today. |
| **P2** | Do this this week. |
| **P3** | Backlog. Do when capacity allows. |

---

## CLI Verbs

Legion exposes 9 verbs, each performing a single operation:

| Verb | Description | Example |
|------|-------------|---------|
| `bootstrap` | Initialize the vault task structure (`tasks/`, `dashboards/`) | `legion bootstrap ~/your-vault/` |
| `capture` | Create a new task from a summary string | `legion capture "Fix broken sync on node-c"` |
| `list` | Show all tasks, with optional filters by status, assignee, project | `legion list --status in_progress` |
| `next` | Get the next available task for a specific agent | `legion next --assignee codex` |
| `claim` | Claim a task (set assignee and status to `in_progress`) | `legion claim TASK-20260412-001 --by claude-code` |
| `update` | Modify a task's status, priority, or other fields | `legion update TASK-20260412-001 --status blocked` |
| `done` | Mark a task as complete, with an optional completion note | `legion done TASK-20260412-001 --note "Merged in PR #42"` |
| `refresh` | Regenerate all dashboard files from current task state | `legion refresh` |
| `doctor` | Validate vault structure, check for orphaned tasks, verify YAML integrity | `legion doctor` |

---

## Agent Lifecycle

The standard agent workflow is five steps:

```
next → claim → work → done → refresh
```

1. **`next`**: The agent asks "What should I work on?" filtered by its own assignee label.
2. **`claim`**: The agent takes ownership, setting `status: in_progress` and `assignee: <self>`.
3. **Work**: The agent performs the task (writes code, runs commands, produces output).
4. **`done`**: The agent marks the task complete with a log entry.
5. **`refresh`**: Dashboards are regenerated to reflect the new state.

Any agent — human or AI — follows the same lifecycle. No special handling per agent type.

---

## MCP Surface

Legion exposes 6 tools via a FastMCP server, enabling programmatic access from any MCP-compatible client:

| Tool | Maps to CLI Verb |
|------|-----------------|
| `capture_task` | `capture` |
| `claim_task` | `claim` |
| `complete_task` | `done` |
| `list_tasks` | `list` |
| `next_tasks` | `next` |
| `refresh_dashboards` | `refresh` |

The MCP server runs alongside the Lazarus (Layer 2) and MemPalace (Layer 1) servers, providing a unified tool surface for AI agents.

---

## Integration with VexNet (Layer 3)

VexNet and Legion are complementary:

- **Session summaries generate tasks**: When a VexNet session summary includes a decision or action item, it can be captured as a Legion task.
- **Task state is visible everywhere**: Because tasks live in the synced vault, every instance on every node sees the same task board.
- **Assignee labels distribute work**: `assignee: codex` means the Codex agent picks it up; `assignee: claude-code` means Claude Code handles it. The human can reassign at any time.
- **Broadcasts can reference tasks**: A VexNet broadcast might say "TASK-20260412-001 is blocked, needs human input" — all instances see it on next self-load.

---

## Design Principles

1. **Markdown is the source of truth.** No hidden database, no plugin state. If you can read the file, you have the full picture.
2. **One contract for all agents.** Human, Claude, Codex, Gemini, Ollama — same YAML schema, same verbs, same lifecycle.
3. **Git-friendly by default.** Date-partitioned directories, unique task IDs, and plain text make for clean version control.
4. **Works without Obsidian.** The task engine is CLI-first. Obsidian is a nice viewer, not a dependency.
5. **Dashboards are derived, not edited.** `refresh` regenerates them. This prevents stale dashboard state.

---

## Getting Started

```bash
# 1. Initialize the task structure in your vault
legion bootstrap ~/your-vault/

# 2. Capture your first task
legion capture "Set up CI/CD pipeline for the project" --priority P1 --project infra

# 3. See what's available
legion list --status ready

# 4. Claim and work
legion claim TASK-20260412-001 --by claude-code

# 5. Complete and refresh
legion done TASK-20260412-001 --note "Pipeline configured in .github/workflows/"
legion refresh
```
