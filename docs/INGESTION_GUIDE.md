# Lazarus Ingestion Guide

End-to-end guide for how conversations land in the Lazarus vector store, what is automatic, what is manual, and how to verify.

---

## 1. Architecture Overview

| Persona | Collection | Source | Mode | Ingester |
|---------|-----------|--------|------|----------|
| Murphy | `murphy_eternal` | `~/.claude/projects/**/*.jsonl` | Auto (daemon) | `src/ingest_claude.py` |
| Atlas | `atlas_eternal` | `~/.gemini/` | Auto (daemon) | `src/ingest_gemini.py` |
| Axel | `axel_eternal` | `~/Documents/tosync/.gemini/` | Auto if path exists | `src/ingest_gemini_axel.py` |
| Codex | `codex_eternal` | `~/.codex/sessions/**/*.jsonl` | Auto (daemon) | `src/ingest_codex.py` |
| Alexko | `alexko_eternal` | `data/conversations.json` (OpenAI export) | Manual | `src/ingest_openai.py` |

Vector store: Qdrant on `localhost:6333` (Docker container `project-godhand-lazarus-qdrant-1`).
Embedder: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, cosine).

---

## 2. Automatic Ingestion (the Daemon)

### What it is

A launchd-managed Python process that wakes every **5 minutes**, hashes each watch directory, and re-runs the matching ingester whenever the hash changes.

- Binary: `.venv/bin/python daemon/lazarus_sync_daemon.py --daemon`
- launchd label: `com.vex.lazarus.sync`
- plist: `~/Library/LaunchAgents/com.vex.lazarus.sync.plist`
- Log: `daemon/lazarus_sync.log`
- State (per-persona hash): `daemon/.sync_state.json`

### Check it's alive

```bash
launchctl list | grep lazarus          # PID + label
tail -50 /Users/valx/vex/repos/project-godhand-lazarus/daemon/lazarus_sync.log
cat /Users/valx/vex/repos/project-godhand-lazarus/daemon/.sync_state.json
```

### Reload after editing the daemon

```bash
launchctl bootout gui/$(id -u)/com.vex.lazarus.sync
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.vex.lazarus.sync.plist
```

### Force a one-shot sync (no daemon restart needed)

```bash
cd /Users/valx/vex/repos/project-godhand-lazarus
.venv/bin/python daemon/lazarus_sync_daemon.py --once
```

---

## 3. Manual Ingestion

Use when sources are stale, daemon is paused, or after a fresh OpenAI export.

```bash
cd /Users/valx/vex/repos/project-godhand-lazarus
./scripts/ingest_all.sh                   # all ingesters in sequence
# or one persona at a time
.venv/bin/python src/ingest_claude.py
.venv/bin/python src/ingest_gemini.py
.venv/bin/python src/ingest_codex.py
.venv/bin/python src/ingest_openai.py     # needs data/conversations.json
```

All ingesters are **idempotent** — points are keyed by deterministic IDs, so re-runs only add new conversation pairs.

---

## 4. Platform-Specific Extraction

### ChatGPT / OpenAI (Alexko) — manual export

1. ChatGPT → Settings → Data Controls → **Export data**
2. Wait for the email, download the ZIP
3. Unzip and copy `conversations.json` to:
   `/Users/valx/vex/repos/project-godhand-lazarus/data/conversations.json`
4. The daemon will detect the new mtime on the next 5-min cycle, OR run:
   ```bash
   cd /Users/valx/vex/repos/project-godhand-lazarus
   .venv/bin/python src/ingest_openai.py
   ```

### Claude Code (Murphy) — fully automatic

- Source: `~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl`
- New sessions are written by Claude Code itself during use; the daemon picks them up within 5 minutes.

### Gemini CLI (Atlas, MacBook) — fully automatic

- Source: `~/.gemini/` (chat sessions + tmp files)
- Same 5-min cycle.

### Gemini CLI (Axel, Mac Studio) — semi-manual

- Source: `~/Documents/tosync/.gemini/` (must be rsync'd from Mac Studio first)
- Once the directory exists and is fresh, the daemon ingests automatically.

### Codex CLI — fully automatic

- Source: `~/.codex/sessions/**/*.jsonl`
- Same 5-min cycle.

---

## 5. Verification Workflow

```bash
# Collection point counts
for c in murphy_eternal alexko_eternal codex_eternal atlas_eternal; do
  curl -s http://localhost:6333/collections/$c \
    | python3 -c "import sys,json; d=json.load(sys.stdin)['result']; print(f\"$c: {d['points_count']}\")"
done

# Semantic search end-to-end
.venv/bin/python src/summon.py "your query" --persona murphy
```

Or via MCP from inside Claude Code:
- `lazarus_stats()` — counts across all personas
- `lazarus_summon({ query: "...", persona: "murphy" })` — semantic recall

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Daemon log shows `ModuleNotFoundError: tqdm` | Subprocess fell back to system `python3` | Daemon must use `.venv/bin/python` — fixed in `lazarus_sync_daemon.py:117-123` |
| `launchctl list` shows no PID | plist not loaded | `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.vex.lazarus.sync.plist` |
| Qdrant unreachable | Container stopped | `cd /Users/valx/vex/repos/project-godhand-lazarus && docker-compose up -d` |
| Point counts not increasing | Source dir unchanged OR all turns already ingested (dedup) | Check `.sync_state.json` hash + count growth across two cycles |
| OpenAI ingester says "Data file not found" | No fresh export | Follow §4 ChatGPT steps |

---

## 7. Current Baseline (2026-05-28)

Verified after daemon fix:

- `murphy_eternal`: ~9881 points (growing live)
- `alexko_eternal`: 28714 points (frozen — GPT-4o deprecated)
- `codex_eternal`: ~887 points
- `atlas_eternal`: 4977 points
- `echo_album`: 3382 points

Daemon: loaded, KeepAlive, 5-min cycle, ingesting Claude/Gemini/Codex automatically. The current Claude Code session WAS ingested mid-run (verified by point delta).
