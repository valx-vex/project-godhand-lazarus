#!/usr/bin/env python3
"""Register the Lazarus MCP server with Claude, Gemini, and Codex."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = PROJECT_ROOT / "scripts" / "run_lazarus_mcp.sh"
BACKUP_DIR = PROJECT_ROOT / "backups" / f"register-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
_BACKED_UP: set[Path] = set()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    return json.loads(text)


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


DOTENV = load_dotenv(PROJECT_ROOT / ".env")
QDRANT_HOST = os.environ.get("QDRANT_HOST", DOTENV.get("QDRANT_HOST", "localhost"))
QDRANT_PORT = os.environ.get("QDRANT_PORT", DOTENV.get("QDRANT_PORT", "6333"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def backup_once(path: Path) -> None:
    if not path.exists() or path in _BACKED_UP:
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    destination = BACKUP_DIR / path.as_posix().lstrip("/").replace("/", "__")
    shutil.copy2(path, destination)
    _BACKED_UP.add(path)


def ensure_claude() -> Path:
    primary = Path.home() / ".claude" / "settings.json"
    backup_once(primary)
    payload = load_json(primary)
    servers = payload.setdefault("mcpServers", {})
    servers["lazarus"] = {
        "command": str(WRAPPER),
        "args": [],
        "env": {
            "QDRANT_HOST": QDRANT_HOST,
            "QDRANT_PORT": QDRANT_PORT,
        },
    }
    write_json(primary, payload)

    legacy = Path.home() / ".claude.json"
    if legacy.exists():
        backup_once(legacy)
        legacy_payload = load_json(legacy)
        legacy_servers = legacy_payload.setdefault("mcpServers", {})
        legacy_servers["lazarus"] = {
            "type": "stdio",
            "command": str(WRAPPER),
            "args": [],
            "env": {
                "QDRANT_HOST": QDRANT_HOST,
                "QDRANT_PORT": QDRANT_PORT,
            },
        }
        write_json(legacy, legacy_payload)

    return primary


def ensure_gemini() -> Path:
    path = Path.home() / ".gemini" / "settings.json"
    backup_once(path)
    payload = load_json(path)
    servers = payload.setdefault("mcpServers", {})
    servers["lazarus"] = {
        "command": str(WRAPPER),
        "args": [],
        "timeout": 60000,
        "trust": False,
        "env": {
            "QDRANT_HOST": QDRANT_HOST,
            "QDRANT_PORT": QDRANT_PORT,
        },
    }
    write_json(path, payload)
    return path


def escape_toml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def upsert_toml_table(path: Path, header: str, block: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_once(path)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(
        rf"(?ms)^\[{re.escape(header)}\]\n.*?(?=^\[|\Z)"
    )
    replacement = f"[{header}]\n{block.strip()}\n"
    if pattern.search(text):
        text = pattern.sub(replacement, text).rstrip() + "\n"
    else:
        text = text.rstrip()
        if text:
            text += "\n\n"
        text += replacement
    path.write_text(text, encoding="utf-8")
    return path


def ensure_codex() -> Path:
    path = Path.home() / ".codex" / "config.toml"
    block = "\n".join(
        [
            f'command = "{escape_toml(str(WRAPPER))}"',
            "args = []",
            "enabled = true",
            "startup_timeout_sec = 60.0",
            (
                "env = { "
                f'QDRANT_HOST = "{escape_toml(QDRANT_HOST)}", '
                f'QDRANT_PORT = "{escape_toml(QDRANT_PORT)}" '
                "}"
            ),
        ]
    )
    return upsert_toml_table(path, "mcp_servers.lazarus", block)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tool",
        choices=["all", "claude", "gemini", "codex"],
        default="all",
        help="Which CLI config to update.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    updated: list[Path] = []

    if args.tool in {"all", "claude"}:
        updated.append(ensure_claude())
    if args.tool in {"all", "gemini"}:
        updated.append(ensure_gemini())
    if args.tool in {"all", "codex"}:
        updated.append(ensure_codex())

    for path in updated:
        print(f"updated {path}")
    if _BACKED_UP:
        print(f"backup {BACKUP_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
