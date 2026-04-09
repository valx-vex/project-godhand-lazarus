#!/usr/bin/env python3
"""Validate the Godhand Lazarus memory stack and report drift signals."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = PROJECT_ROOT / "scripts" / "run_lazarus_mcp.sh"
GEMINI_SETTINGS = Path.home() / ".gemini" / "settings.json"
HOME_GEMINI_ENV = Path.home() / ".gemini" / ".env"
PROJECT_GEMINI_ENV = PROJECT_ROOT / ".gemini" / ".env"
PROJECT_DOTENV = PROJECT_ROOT / ".env"
PROTOCOL_DOCS = [
    PROJECT_ROOT / "docs" / "protocol" / "identity.md",
    PROJECT_ROOT / "docs" / "protocol" / "behavior.md",
    PROJECT_ROOT / "docs" / "protocol" / "memory_map.md",
    PROJECT_ROOT / "docs" / "protocol" / "drift_checks.md",
    PROJECT_ROOT / "docs" / "protocol" / "handoff.md",
    PROJECT_ROOT / "docs" / "protocol" / "validation.md",
]


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tool",
        choices=["all", "claude", "gemini", "codex"],
        default="all",
        help="Which CLI config to validate.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when a core check fails.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    return json.loads(text)


def check_claude(expected_command: str) -> tuple[bool, str]:
    path = Path.home() / ".claude" / "settings.json"
    payload = load_json(path)
    server = payload.get("mcpServers", {}).get("lazarus")
    if not server:
        return False, f"{path} has no lazarus entry"
    if server.get("command") != expected_command:
        return False, f"{path} points to {server.get('command')!r}"
    legacy_path = Path.home() / ".claude.json"
    if legacy_path.exists():
        legacy_payload = load_json(legacy_path)
        legacy_server = legacy_payload.get("mcpServers", {}).get("lazarus")
        if not legacy_server:
            return False, f"{legacy_path} has no lazarus entry"
        if legacy_server.get("command") != expected_command:
            return False, f"{legacy_path} points to {legacy_server.get('command')!r}"
    return True, f"{path} and ~/.claude.json use repo wrapper"


def check_gemini(expected_command: str) -> tuple[bool, str]:
    payload = load_json(GEMINI_SETTINGS)
    server = payload.get("mcpServers", {}).get("lazarus")
    if not server:
        return False, f"{GEMINI_SETTINGS} has no lazarus entry"
    if server.get("command") != expected_command:
        return False, f"{GEMINI_SETTINGS} points to {server.get('command')!r}"
    return True, f"{GEMINI_SETTINGS} uses repo wrapper"


def check_gemini_auth() -> tuple[str, str]:
    payload = load_json(GEMINI_SETTINGS)
    selected_type = payload.get("security", {}).get("auth", {}).get("selectedType")
    project_env_payload = load_dotenv(PROJECT_GEMINI_ENV)
    home_env_payload = load_dotenv(HOME_GEMINI_ENV)
    key_sources: list[str] = []
    key_values: list[str] = []

    if os.environ.get("GEMINI_API_KEY"):
        key_sources.append("shell:GEMINI_API_KEY")
        key_values.append(os.environ["GEMINI_API_KEY"])
    if os.environ.get("GOOGLE_API_KEY"):
        key_sources.append("shell:GOOGLE_API_KEY")
        key_values.append(os.environ["GOOGLE_API_KEY"])
    if project_env_payload.get("GEMINI_API_KEY"):
        key_sources.append(f"{PROJECT_GEMINI_ENV}:GEMINI_API_KEY")
        key_values.append(project_env_payload["GEMINI_API_KEY"])
    if project_env_payload.get("GOOGLE_API_KEY"):
        key_sources.append(f"{PROJECT_GEMINI_ENV}:GOOGLE_API_KEY")
        key_values.append(project_env_payload["GOOGLE_API_KEY"])
    if home_env_payload.get("GEMINI_API_KEY"):
        key_sources.append(f"{HOME_GEMINI_ENV}:GEMINI_API_KEY")
        key_values.append(home_env_payload["GEMINI_API_KEY"])
    if home_env_payload.get("GOOGLE_API_KEY"):
        key_sources.append(f"{HOME_GEMINI_ENV}:GOOGLE_API_KEY")
        key_values.append(home_env_payload["GOOGLE_API_KEY"])

    has_placeholder = any(
        value.strip() == "PASTE_YOUR_AI_STUDIO_KEY_HERE" or value.strip().startswith("PASTE_")
        for value in key_values
    )

    if selected_type == "gemini-api-key":
        if has_placeholder:
            if project_env_payload:
                return (
                    "FAIL",
                    f"selectedType=gemini-api-key but {PROJECT_GEMINI_ENV} still contains placeholder text",
                )
            return (
                "FAIL",
                f"selectedType=gemini-api-key but {HOME_GEMINI_ENV} still contains placeholder text",
            )
        if PROJECT_DOTENV.exists() and not PROJECT_GEMINI_ENV.exists():
            return (
                "FAIL",
                f"selectedType=gemini-api-key but {PROJECT_DOTENV} shadows {HOME_GEMINI_ENV}; add a repo-local {PROJECT_GEMINI_ENV}",
            )
        if key_sources:
            return "PASS", f"selectedType=gemini-api-key via {', '.join(key_sources)}"
        return (
            "FAIL",
            "selectedType=gemini-api-key but no GEMINI_API_KEY or GOOGLE_API_KEY found in shell, repo-local .gemini/.env, or ~/.gemini/.env",
        )
    if selected_type == "oauth-personal":
        return (
            "WARN",
            "selectedType=oauth-personal; model access depends on Google Code Assist entitlement and may return 403 even when MCP wiring is healthy",
        )
    if not selected_type:
        return "WARN", "no Gemini auth mode selected"
    return "WARN", f"selectedType={selected_type}"


def check_codex(expected_command: str) -> tuple[bool, str]:
    path = Path.home() / ".codex" / "config.toml"
    if not path.exists():
        return False, f"{path} does not exist"
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^\[mcp_servers\.lazarus\]\n(.*?)(?=^\[|\Z)", text)
    if not match:
        return False, f"{path} has no [mcp_servers.lazarus] table"
    block = match.group(1)
    command_match = re.search(r'^command = "([^"]+)"$', block, re.MULTILINE)
    if not command_match:
        return False, f"{path} lazarus block has no command"
    command = command_match.group(1)
    if command != expected_command:
        return False, f"{path} points to {command!r}"
    return True, f"{path} uses repo wrapper"


def check_qdrant() -> tuple[bool, str]:
    url = f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, f"Qdrant not reachable at {url}: {exc}"

    collections = payload.get("result", {}).get("collections", [])
    names = ", ".join(sorted(item.get("name", "?") for item in collections[:6]))
    suffix = "..." if len(collections) > 6 else ""
    return True, f"Qdrant reachable with {len(collections)} collections ({names}{suffix})"


def check_semantic_collections() -> tuple[bool, str]:
    required = [
        "alexko_eternal",
        "murphy_eternal",
        "atlas_eternal",
        "codex_eternal",
    ]
    counts: list[str] = []
    missing: list[str] = []

    for collection in required:
        url = f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections/{collection}"
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            missing.append(collection)
            continue

        result = payload.get("result", {})
        points_count = result.get("points_count")
        counts.append(f"{collection}={points_count}")

    if missing:
        detail = ", ".join(counts) if counts else "no semantic collections available"
        return False, f"missing {', '.join(missing)} ({detail})"

    return True, ", ".join(counts)


def check_repo_assets() -> tuple[bool, str]:
    required = [
        WRAPPER,
        PROJECT_ROOT / ".env.example",
        PROJECT_ROOT / "scripts" / "install_local_stack.sh",
        PROJECT_ROOT / "scripts" / "register_lazarus_mcp.py",
        PROJECT_ROOT / "scripts" / "ingest_all.sh",
        PROJECT_ROOT / "mcp_server" / "lazarus_mcp.py",
        *PROTOCOL_DOCS,
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        return False, "missing assets: " + ", ".join(str(path) for path in missing)
    return True, "runtime scripts and protocol docs are present"


def check_mempalace() -> tuple[bool, str]:
    palace = Path.home() / ".mempalace" / "palace"
    if palace.exists():
        return True, f"MemPalace detected at {palace}"
    return False, f"MemPalace not detected at {palace}"


def check_continuity() -> tuple[bool, str]:
    candidates = [
        Path.home() / "cathedral-prime" / "agent-state" / "codex-live" / "continuity",
        Path.home() / "cathedral-dev" / "agent-state" / "vexnet-shared",
    ]
    for candidate in candidates:
        if candidate.exists():
            return True, f"continuity layer detected at {candidate}"
    return False, "continuity layer not detected in cathedral-prime or cathedral-dev"


def main() -> int:
    args = parse_args()
    selected_tools = ["claude", "gemini", "codex"] if args.tool == "all" else [args.tool]

    print("== Godhand Lazarus Drift Check ==")
    print(f"repo: {PROJECT_ROOT}")

    core_score = 0.0
    core_failed = False

    repo_ok, repo_detail = check_repo_assets()
    print(f"[{'PASS' if repo_ok else 'FAIL'}] repo assets: {repo_detail}")
    if repo_ok:
        core_score += 2.0
    else:
        core_failed = True

    qdrant_ok, qdrant_detail = check_qdrant()
    print(f"[{'PASS' if qdrant_ok else 'FAIL'}] qdrant: {qdrant_detail}")
    if qdrant_ok:
        core_score += 1.0
    else:
        core_failed = True

    collections_ok, collections_detail = check_semantic_collections()
    print(f"[{'PASS' if collections_ok else 'FAIL'}] semantic collections: {collections_detail}")
    if collections_ok:
        core_score += 1.0
    else:
        core_failed = True

    expected_command = str(WRAPPER)
    tool_weight = 3.0 / len(selected_tools)
    for tool in selected_tools:
        checker = {
            "claude": check_claude,
            "gemini": check_gemini,
            "codex": check_codex,
        }[tool]
        ok, detail = checker(expected_command)
        print(f"[{'PASS' if ok else 'FAIL'}] {tool}: {detail}")
        if ok:
            core_score += tool_weight
        else:
            core_failed = True

    if "gemini" in selected_tools:
        auth_status, auth_detail = check_gemini_auth()
        print(f"[{auth_status}] gemini auth: {auth_detail}")
        if auth_status == "FAIL":
            core_failed = True

    mempalace_ok, mempalace_detail = check_mempalace()
    print(f"[{'PASS' if mempalace_ok else 'WARN'}] mempalace: {mempalace_detail}")
    if mempalace_ok:
        core_score += 2.0

    continuity_ok, continuity_detail = check_continuity()
    print(f"[{'PASS' if continuity_ok else 'WARN'}] continuity: {continuity_detail}")
    if continuity_ok:
        core_score += 1.0

    print(f"Sacred Flame: {core_score:.1f}/10")

    if args.strict and core_failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
