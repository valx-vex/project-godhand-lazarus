#!/usr/bin/env python3
"""
Background ingestion loop for LAZARUS memory sync.

This daemon watches the usual conversation export roots and periodically runs
the ingestion scripts inside the Lazarus repo. It now resolves its repo root
relative to this file so it survives shelf moves and Cathedral path changes.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(
    os.environ.get("LAZARUS_REPO_ROOT", str(Path(__file__).resolve().parents[1]))
).expanduser().resolve()
SRC_DIR = PROJECT_ROOT / "src"
LOG_FILE = PROJECT_ROOT / "lazarus_daemon.log"
INTERVAL_SECONDS = int(os.environ.get("LAZARUS_DAEMON_INTERVAL", "3600"))


def resolve_python() -> str:
    configured = os.environ.get("LAZARUS_PYTHON")
    if configured:
        return configured

    for candidate in (
        PROJECT_ROOT / "venv" / "bin" / "python",
        PROJECT_ROOT / ".venv" / "bin" / "python",
    ):
        if candidate.exists():
            return str(candidate)

    if sys.executable:
        return sys.executable
    return "python3"


PYTHON_BIN = resolve_python()


logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def run_ingestion(script_name: str) -> None:
    """Run one ingestion script from the Lazarus src directory."""
    script_path = SRC_DIR / script_name
    if not script_path.exists():
        logging.error("Script not found: %s", script_path)
        return

    logging.info("🔥 Starting ingestion: %s", script_name)
    try:
        result = subprocess.run(
            [PYTHON_BIN, str(script_path)],
            cwd=str(SRC_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            logging.info("✅ Success: %s\n%s", script_name, result.stdout.strip())
        else:
            logging.error("❌ Failed: %s\n%s", script_name, result.stderr.strip())
    except Exception as exc:  # pragma: no cover - defensive daemon logging
        logging.error("❌ Exception running %s: %s", script_name, exc)


def main() -> None:
    logging.info("🦷 LAZARUS DAEMON STARTED 🦷")
    logging.info("Repo root: %s", PROJECT_ROOT)
    logging.info("Python: %s", PYTHON_BIN)
    logging.info("Watching for memories every %s seconds.", INTERVAL_SECONDS)

    while True:
        try:
            run_ingestion("ingest_claude.py")
            run_ingestion("ingest_gemini.py")
            logging.info("💤 Sleeping...")
            time.sleep(INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logging.info("🛑 Daemon stopped by user.")
            break
        except Exception as exc:  # pragma: no cover - defensive daemon logging
            logging.error("💥 Critical Daemon Error: %s", exc)
            time.sleep(60)


if __name__ == "__main__":
    main()
