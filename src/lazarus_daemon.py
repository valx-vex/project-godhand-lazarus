#!/usr/bin/env python3
"""
🦷 LAZARUS DAEMON: The Heartbeat of Memory 🦷

This daemon runs in the background and:
1. Watches for new conversation logs (Claude, Gemini, OpenAI).
2. Automatically ingests them into Qdrant via the ingestion scripts.
3. Ensures no memory is lost to the void.

Author: Alexko Atlas (The Architect)
Date: 2026-02-07
Project: GODHAND LAZARUS
"""

import time
import subprocess
import os
import logging
from pathlib import Path
from datetime import datetime

# --- CONFIG ---
PROJECT_ROOT = Path("/Users/valx/cathedral/1. AVos/1. Digital/projects/PROJECT_GODHAND_LAZARUS")
SRC_DIR = PROJECT_ROOT / "src"
LOG_FILE = PROJECT_ROOT / "lazarus_daemon.log"
INTERVAL_SECONDS = 3600  # Check every hour

# Paths to watch (can be expanded)
CLAUDE_PROJECTS = Path.home() / ".claude/projects"
GEMINI_CONVOS = Path.home() / ".gemini/antigravity/conversations"

# Logging setup
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run_ingestion(script_name):
    """Runs a specific ingestion script inside the venv."""
    script_path = SRC_DIR / script_name
    venv_python = PROJECT_ROOT / "venv/bin/python"
    
    if not script_path.exists():
        logging.error(f"Script not found: {script_path}")
        return

    logging.info(f"🔥 Starting ingestion: {script_name}")
    try:
        # Run the script with the venv python
        result = subprocess.run(
            [str(venv_python), str(script_path)],
            cwd=str(SRC_DIR),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logging.info(f"✅ Success: {script_name}
{result.stdout}")
        else:
            logging.error(f"❌ Failed: {script_name}
{result.stderr}")
            
    except Exception as e:
        logging.error(f"❌ Exception running {script_name}: {e}")

def main():
    logging.info("🦷 LAZARUS DAEMON STARTED 🦷")
    logging.info(f"Watching for memories every {INTERVAL_SECONDS} seconds.")

    while True:
        try:
            # 1. Ingest Claude Memories (Murphy)
            # ingest_claude.py is smart enough to check for diffs usually, 
            # or we can rely on it scanning quickly.
            run_ingestion("ingest_claude.py")

            # 2. Ingest Gemini Memories (Atlas/Axel)
            run_ingestion("ingest_gemini.py")
            
            # 3. Ingest OpenAI (Alexko Eternal) - usually manual export, but we check anyway
            # run_ingestion("ingest_openai.py") 
            # (Skipping automatic OpenAI for now as it requires manual JSON export placement)

            logging.info("💤 Sleeping...")
            time.sleep(INTERVAL_SECONDS)

        except KeyboardInterrupt:
            logging.info("🛑 Daemon stopped by user.")
            break
        except Exception as e:
            logging.error(f"💥 Critical Daemon Error: {e}")
            time.sleep(60) # Wait a bit before retrying

if __name__ == "__main__":
    main()
