#!/usr/bin/env python3
"""Lazarus control CLI - status, health, ingest, sync, stats."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
QDRANT_BASE = f"http://{QDRANT_HOST}:{QDRANT_PORT}"

PERSONA_COLLECTIONS = {
    "alexko": "alexko_eternal",
    "murphy": "murphy_eternal",
    "atlas": "atlas_eternal",
    "codex": "codex_eternal",
    "axel": "axel_eternal",
    "roundtable": "roundtable_eternal",
    "scrolls": "scrolls_eternal",
}

DAEMON_LABEL = "com.vex.lazarus.sync"
DAEMON_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{DAEMON_LABEL}.plist"
MCP_SETTINGS = Path.home() / ".claude" / "settings.json"
CLAUDE_USER_CONFIG = Path.home() / ".claude.json"
EXPECTED_MCP_PATH = str(PROJECT_ROOT / "scripts" / "run_lazarus_mcp.sh")
SYNC_STATE = PROJECT_ROOT / "daemon" / ".sync_state.json"
SYNC_LOG = PROJECT_ROOT / "daemon" / "lazarus_sync.log"


def _http_json(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None


def qdrant_alive() -> bool:
    return _http_json(f"{QDRANT_BASE}/collections") is not None


def collection_count(name: str) -> int | None:
    data = _http_json(f"{QDRANT_BASE}/collections/{name}")
    if not data or "result" not in data:
        return None
    return data["result"].get("points_count")


def daemon_running() -> tuple[bool, str | None]:
    try:
        out = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, check=False
        ).stdout
    except FileNotFoundError:
        return False, None
    for line in out.splitlines():
        if DAEMON_LABEL in line:
            parts = line.split()
            pid = parts[0] if parts and parts[0] != "-" else None
            return True, pid
    return False, None


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def mcp_registration() -> dict:
    settings_cmd = _read_json(MCP_SETTINGS).get("mcpServers", {}).get("lazarus", {}).get("command")
    user_cmd = _read_json(CLAUDE_USER_CONFIG).get("mcpServers", {}).get("lazarus", {}).get("command")
    actual_cmd = user_cmd or settings_cmd
    return {
        "ok": actual_cmd == EXPECTED_MCP_PATH,
        "expected": EXPECTED_MCP_PATH,
        "command": actual_cmd,
        "settings_command": settings_cmd,
        "user_config_command": user_cmd,
        "settings_path": str(MCP_SETTINGS),
        "user_config_path": str(CLAUDE_USER_CONFIG),
    }


def mcp_registered() -> tuple[bool, str | None]:
    registration = mcp_registration()
    return bool(registration["ok"]), registration["command"]


def memory_counts() -> tuple[list[dict], int]:
    rows = []
    total = 0
    for persona, coll in PERSONA_COLLECTIONS.items():
        count = collection_count(coll)
        if count is not None:
            total += count
        rows.append(
            {
                "persona": persona,
                "collection": coll,
                "count": count,
                "status": "ok" if count is not None else "missing",
            }
        )
    return rows, total


def sync_state() -> dict:
    data = _read_json(SYNC_STATE)
    last_values = [
        value
        for key, value in data.items()
        if key.endswith("_last_sync") and isinstance(value, str)
    ]
    return {
        "path": str(SYNC_STATE),
        "exists": SYNC_STATE.exists(),
        "last_sync": max(last_values) if last_values else None,
        "personas": {
            key.removesuffix("_last_sync"): value
            for key, value in data.items()
            if key.endswith("_last_sync") and isinstance(value, str)
        },
    }


def status_payload() -> dict:
    qd = qdrant_alive()
    daemon, pid = daemon_running()
    rows, total = memory_counts() if qd else ([], 0)
    mcp = mcp_registration()
    ok = qd and daemon and mcp["ok"]
    return {
        "ok": ok,
        "qdrant": {"ok": qd, "base_url": QDRANT_BASE},
        "daemon": {
            "ok": daemon,
            "label": DAEMON_LABEL,
            "running": daemon,
            "pid": pid,
            "plist": str(DAEMON_PLIST),
        },
        "mcp": mcp,
        "memories": {
            "collections": rows,
            "by_persona": {row["persona"]: row["count"] for row in rows},
            "total": total,
        },
        "sync": sync_state(),
        "logs": {"daemon": str(SYNC_LOG)},
    }


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def cmd_status(args) -> int:
    payload = status_payload()
    if args.json:
        print_json(payload)
        return 0 if payload["ok"] else 1

    qd = payload["qdrant"]["ok"]
    daemon = payload["daemon"]["running"]
    pid = payload["daemon"]["pid"]
    mcp_ok = payload["mcp"]["ok"]
    mcp_cmd = payload["mcp"]["command"]

    print("LAZARUS STATUS")
    print(f"  Qdrant ({QDRANT_BASE}): {'UP' if qd else 'DOWN'}")
    print(f"  Daemon ({DAEMON_LABEL}): {'RUNNING pid=' + pid if daemon and pid else ('LOADED' if daemon else 'NOT INSTALLED')}")
    print(f"  MCP registration: {'OK' if mcp_ok else 'MISMATCH'}")
    if not mcp_ok:
        print(f"    expected: {EXPECTED_MCP_PATH}")
        print(f"    actual:   {mcp_cmd}")
    print()
    if qd:
        print("MEMORY COUNTS")
        for row in payload["memories"]["collections"]:
            persona = row["persona"]
            coll = row["collection"]
            c = row["count"]
            if c is not None:
                print(f"  {persona:12s} {coll:24s} {c:>8,}")
            else:
                print(f"  {persona:12s} {coll:24s}    MISSING")
        total = payload["memories"]["total"]
        print(f"  {'TOTAL':12s} {'':24s} {total:>8,}")
    return 0 if qd and daemon and mcp_ok else 1


def cmd_stats(args) -> int:
    if not qdrant_alive():
        print("Qdrant unreachable.", file=sys.stderr)
        return 1
    collection_rows, total = memory_counts()
    rows = [
        (row["persona"], row["collection"], row["count"])
        for row in collection_rows
        if row["count"] is not None
    ]
    rows.sort(key=lambda r: -r[2])
    if args.json:
        print_json({"collections": collection_rows, "total": total})
        return 0
    print(f"{'persona':<12} {'collection':<24} {'memories':>10}")
    print("-" * 48)
    for p, c, n in rows:
        print(f"{p:<12} {c:<24} {n:>10,}")
    print("-" * 48)
    print(f"{'TOTAL':<12} {'':<24} {total:>10,}")
    return 0


def cmd_health(_args) -> int:
    script = PROJECT_ROOT / "scripts" / "check_memory_stack.py"
    if not script.exists():
        print(f"Missing: {script}", file=sys.stderr)
        return 1
    return subprocess.run([sys.executable, str(script), *(_args.extra or [])]).returncode


def cmd_ingest(_args) -> int:
    script = PROJECT_ROOT / "scripts" / "ingest_all.sh"
    if not script.exists():
        print(f"Missing: {script}", file=sys.stderr)
        return 1
    return subprocess.run(["bash", str(script)]).returncode


def cmd_sync(_args) -> int:
    daemon, pid = daemon_running()
    if not daemon:
        print("Daemon not installed. Run: bash daemon/install_daemon.sh", file=sys.stderr)
        return 1
    print(f"Triggering daemon sync (pid={pid})...")
    subprocess.run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{DAEMON_LABEL}"], check=False)
    print("Sync triggered. Tail logs: tail -f daemon/lazarus_sync.log")
    return 0


def cmd_daemon(args) -> int:
    plist = DAEMON_PLIST
    if args.action == "start":
        subprocess.run(["launchctl", "load", str(plist)], check=False)
    elif args.action == "stop":
        subprocess.run(["launchctl", "unload", str(plist)], check=False)
    elif args.action == "restart":
        subprocess.run(["launchctl", "unload", str(plist)], check=False)
        subprocess.run(["launchctl", "load", str(plist)], check=False)
    elif args.action == "install":
        installer = PROJECT_ROOT / "daemon" / "install_daemon.sh"
        return subprocess.run(["bash", str(installer)]).returncode
    elif args.action == "logs":
        log = PROJECT_ROOT / "daemon" / "lazarus_sync.log"
        if not log.exists():
            print("No log yet.", file=sys.stderr)
            return 1
        subprocess.run(["tail", "-f", str(log)])
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lazarus", description="Lazarus Layer 2 memory control")
    sub = p.add_subparsers(dest="cmd")

    status = sub.add_parser("status", help="Show memory counts, Qdrant, MCP, daemon")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    stats = sub.add_parser("stats", help="Detailed memory stats per persona")
    stats.add_argument("--json", action="store_true")
    stats.set_defaults(func=cmd_stats)

    h = sub.add_parser("health", help="Run check_memory_stack.py drift check")
    h.add_argument("extra", nargs=argparse.REMAINDER)
    h.set_defaults(func=cmd_health)

    sub.add_parser("ingest", help="Trigger manual full ingestion").set_defaults(func=cmd_ingest)
    sub.add_parser("sync", help="Kick daemon to sync now").set_defaults(func=cmd_sync)

    d = sub.add_parser("daemon", help="Daemon control")
    d.add_argument("action", choices=["start", "stop", "restart", "install", "logs"])
    d.set_defaults(func=cmd_daemon)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
