#!/usr/bin/env python3
"""
🦷💀🔥 LAZARUS AUTO-SYNC DAEMON 🔥💀🦷

Continuously monitors and ingests new conversations into the LAZARUS database.

Watches:
- ~/.claude/projects/ (Murphy sessions - auto)
- ~/.gemini/ (Atlas sessions - auto)
- ~/.codex/sessions/ (Codex sessions - auto)
- ~/Documents/tosync/.gemini/ (Axel sessions - manual sync from Mac Studio)
- ~/cathedral/.../data/conversations.json (Alexko - manual OpenAI export)

Runs as a background daemon via launchd on macOS.

Author: Murphy (Claude Code)
Date: 2026-01-31
"""

import os
import sys
import time
import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# --- CONFIG ---
CHECK_INTERVAL = 300  # Check every 5 minutes
LOG_FILE = PROJECT_ROOT / "daemon" / "lazarus_sync.log"
STATE_FILE = PROJECT_ROOT / "daemon" / ".sync_state.json"

INGESTERS = {
    "murphy": {
        "script": PROJECT_ROOT / "src" / "ingest_claude.py",
        "watch_path": Path.home() / ".claude" / "projects",
        "description": "Claude Code sessions"
    },
    "atlas": {
        "script": PROJECT_ROOT / "src" / "ingest_gemini.py",
        "watch_path": Path.home() / ".gemini",
        "description": "Gemini CLI sessions (MacBook)"
    },
    "axel": {
        "script": PROJECT_ROOT / "src" / "ingest_gemini_axel.py",
        "watch_path": Path.home() / "Documents" / "tosync" / ".gemini",
        "description": "Gemini CLI sessions (Mac Studio synced)"
    },
    "codex": {
        "script": PROJECT_ROOT / "src" / "ingest_codex.py",
        "watch_path": Path.home() / ".codex" / "sessions",
        "description": "GPT-4 Codex CLI sessions"
    }
    # Note: Alexko (OpenAI) requires manual export - check separately
}


def log(message: str):
    """Log a message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)

    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")


def get_directory_hash(path: Path) -> str:
    """Get a hash of directory contents (file names + mtimes)."""
    if not path.exists():
        return "not_found"

    hasher = hashlib.md5()
    for root, dirs, files in os.walk(path):
        for fname in sorted(files):
            fpath = Path(root) / fname
            try:
                mtime = fpath.stat().st_mtime
                hasher.update(f"{fpath}:{mtime}".encode())
            except:
                pass

    return hasher.hexdigest()


def load_state() -> dict:
    """Load previous sync state."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    """Save current sync state."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def run_ingester(persona: str, config: dict) -> bool:
    """Run an ingester script."""
    script = config["script"]

    if not script.exists():
        log(f"  ❌ Script not found: {script}")
        return False

    log(f"  🔄 Running {persona} ingester...")

    try:
        # Activate venv and run script
        venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
        if not venv_python.exists():
            venv_python = "python3"
        else:
            venv_python = str(venv_python)

        result = subprocess.run(
            [venv_python, str(script)],
            cwd=str(PROJECT_ROOT / "src"),
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        # Log output
        if result.stdout:
            for line in result.stdout.strip().split("\n")[-5:]:  # Last 5 lines
                log(f"    {line}")

        if result.returncode == 0:
            log(f"  ✅ {persona} ingestion complete!")
            return True
        else:
            log(f"  ❌ {persona} ingestion failed: {result.stderr[:200]}")
            return False

    except subprocess.TimeoutExpired:
        log(f"  ⏰ {persona} ingestion timed out!")
        return False
    except Exception as e:
        log(f"  ❌ {persona} error: {e}")
        return False


def check_and_sync():
    """Check for changes and sync if needed."""
    log("🦷 LAZARUS SYNC CHECK")

    state = load_state()
    changes_detected = False

    for persona, config in INGESTERS.items():
        watch_path = config["watch_path"]
        current_hash = get_directory_hash(watch_path)
        previous_hash = state.get(f"{persona}_hash", "")

        if current_hash != previous_hash and current_hash != "not_found":
            log(f"📝 Changes detected in {persona} ({config['description']})")
            changes_detected = True

            if run_ingester(persona, config):
                state[f"{persona}_hash"] = current_hash
                state[f"{persona}_last_sync"] = datetime.now().isoformat()

    # Check for Alexko (manual OpenAI export)
    alexko_export = PROJECT_ROOT / "data" / "conversations.json"
    if alexko_export.exists():
        current_mtime = alexko_export.stat().st_mtime
        previous_mtime = state.get("alexko_mtime", 0)

        if current_mtime > previous_mtime:
            log(f"📝 New Alexko export detected!")
            changes_detected = True

            # Run OpenAI ingester
            script = PROJECT_ROOT / "src" / "ingest_openai.py"
            if run_ingester("alexko", {"script": script, "description": "OpenAI export"}):
                state["alexko_mtime"] = current_mtime
                state["alexko_last_sync"] = datetime.now().isoformat()

    if changes_detected:
        save_state(state)
        log("✅ Sync state saved")
    else:
        log("💤 No changes detected")

    log("")


def daemon_loop():
    """Main daemon loop."""
    log("")
    log("=" * 60)
    log("🦷💀🔥 LAZARUS AUTO-SYNC DAEMON STARTED 🔥💀🦷")
    log(f"Check interval: {CHECK_INTERVAL} seconds")
    log(f"Log file: {LOG_FILE}")
    log("=" * 60)
    log("")

    # Create log directory if needed
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            check_and_sync()
        except Exception as e:
            log(f"❌ ERROR in sync loop: {e}")

        time.sleep(CHECK_INTERVAL)


def run_once():
    """Run sync once and exit (for testing)."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    check_and_sync()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LAZARUS Auto-Sync Daemon")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon loop")

    args = parser.parse_args()

    if args.once:
        run_once()
    elif args.daemon:
        daemon_loop()
    else:
        print("Usage: lazarus_sync_daemon.py [--once | --daemon]")
        print("  --once   Run sync once and exit")
        print("  --daemon Run continuous sync loop")
