#!/usr/bin/env python3
"""Switch Gemini CLI auth modes for the local operator install."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = Path.home() / ".gemini" / "settings.json"
HOME_ENV_PATH = Path.home() / ".gemini" / ".env"
PROJECT_ENV_PATH = PROJECT_ROOT / ".gemini" / ".env"
PROJECT_DOTENV_PATH = PROJECT_ROOT / ".env"
BACKUP_DIR = PROJECT_ROOT / "backups" / f"gemini-auth-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    return json.loads(text)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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


def backup_once(path: Path) -> None:
    if not path.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    destination = BACKUP_DIR / path.as_posix().lstrip("/").replace("/", "__")
    shutil.copy2(path, destination)


def key_sources() -> list[str]:
    sources: list[str] = []
    shell_key = os.environ.get("GEMINI_API_KEY")
    if shell_key and not is_invalid_key(shell_key):
        sources.append("shell:GEMINI_API_KEY")
    shell_google_key = os.environ.get("GOOGLE_API_KEY")
    if shell_google_key and not is_invalid_key(shell_google_key):
        sources.append("shell:GOOGLE_API_KEY")
    project_dotenv = load_dotenv(PROJECT_ENV_PATH)
    project_key = project_dotenv.get("GEMINI_API_KEY")
    if project_key and not is_invalid_key(project_key):
        sources.append(f"{PROJECT_ENV_PATH}:GEMINI_API_KEY")
    project_google_key = project_dotenv.get("GOOGLE_API_KEY")
    if project_google_key and not is_invalid_key(project_google_key):
        sources.append(f"{PROJECT_ENV_PATH}:GOOGLE_API_KEY")
    dotenv = load_dotenv(HOME_ENV_PATH)
    home_key = dotenv.get("GEMINI_API_KEY")
    if home_key and not is_invalid_key(home_key):
        sources.append(f"{HOME_ENV_PATH}:GEMINI_API_KEY")
    home_google_key = dotenv.get("GOOGLE_API_KEY")
    if home_google_key and not is_invalid_key(home_google_key):
        sources.append(f"{HOME_ENV_PATH}:GOOGLE_API_KEY")
    return sources


def is_placeholder(value: str | None) -> bool:
    if not value:
        return False
    stripped = value.strip()
    return stripped == "PASTE_YOUR_AI_STUDIO_KEY_HERE" or stripped.startswith("PASTE_")


def is_invalid_key(value: str | None) -> bool:
    if not value:
        return False
    stripped = value.strip()
    if is_placeholder(stripped):
        return True
    if any(character.isspace() for character in stripped):
        return True
    if stripped.startswith("printf "):
        return True
    if "gemini -p" in stripped or "configure_gemini_auth.py" in stripped:
        return True
    return False


def invalid_key_sources() -> list[str]:
    sources: list[str] = []
    if is_invalid_key(os.environ.get("GEMINI_API_KEY")):
        sources.append("shell:GEMINI_API_KEY")
    if is_invalid_key(os.environ.get("GOOGLE_API_KEY")):
        sources.append("shell:GOOGLE_API_KEY")

    project_dotenv = load_dotenv(PROJECT_ENV_PATH)
    if is_invalid_key(project_dotenv.get("GEMINI_API_KEY")):
        sources.append(f"{PROJECT_ENV_PATH}:GEMINI_API_KEY")
    if is_invalid_key(project_dotenv.get("GOOGLE_API_KEY")):
        sources.append(f"{PROJECT_ENV_PATH}:GOOGLE_API_KEY")

    home_dotenv = load_dotenv(HOME_ENV_PATH)
    if is_invalid_key(home_dotenv.get("GEMINI_API_KEY")):
        sources.append(f"{HOME_ENV_PATH}:GEMINI_API_KEY")
    if is_invalid_key(home_dotenv.get("GOOGLE_API_KEY")):
        sources.append(f"{HOME_ENV_PATH}:GOOGLE_API_KEY")
    return sources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["gemini-api-key", "oauth-personal"],
        required=True,
        help="The Gemini CLI auth mode to select.",
    )
    return parser.parse_args()


def write_dotenv(path: Path, key_name: str, key_value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{key_name}={key_value.strip()}\n", encoding="utf-8")


def best_available_key() -> tuple[str | None, str | None, str | None]:
    shell_key = os.environ.get("GEMINI_API_KEY")
    if shell_key and not is_invalid_key(shell_key):
        return "GEMINI_API_KEY", shell_key, "shell:GEMINI_API_KEY"
    shell_google_key = os.environ.get("GOOGLE_API_KEY")
    if shell_google_key and not is_invalid_key(shell_google_key):
        return "GOOGLE_API_KEY", shell_google_key, "shell:GOOGLE_API_KEY"

    project_dotenv = load_dotenv(PROJECT_ENV_PATH)
    project_key = project_dotenv.get("GEMINI_API_KEY")
    if project_key and not is_invalid_key(project_key):
        return "GEMINI_API_KEY", project_key, f"{PROJECT_ENV_PATH}:GEMINI_API_KEY"
    project_google_key = project_dotenv.get("GOOGLE_API_KEY")
    if project_google_key and not is_invalid_key(project_google_key):
        return "GOOGLE_API_KEY", project_google_key, f"{PROJECT_ENV_PATH}:GOOGLE_API_KEY"

    home_dotenv = load_dotenv(HOME_ENV_PATH)
    home_key = home_dotenv.get("GEMINI_API_KEY")
    if home_key and not is_invalid_key(home_key):
        return "GEMINI_API_KEY", home_key, f"{HOME_ENV_PATH}:GEMINI_API_KEY"
    home_google_key = home_dotenv.get("GOOGLE_API_KEY")
    if home_google_key and not is_invalid_key(home_google_key):
        return "GOOGLE_API_KEY", home_google_key, f"{HOME_ENV_PATH}:GOOGLE_API_KEY"

    return None, None, None


def sync_project_env() -> tuple[bool, str]:
    key_name, key_value, source = best_available_key()
    if not key_name or not key_value:
        return False, "no key available to write into repo-local .gemini/.env"

    existing = load_dotenv(PROJECT_ENV_PATH)
    existing_value = existing.get("GEMINI_API_KEY") or existing.get("GOOGLE_API_KEY")
    if existing_value and not is_invalid_key(existing_value):
        existing_name = "GEMINI_API_KEY" if existing.get("GEMINI_API_KEY") else "GOOGLE_API_KEY"
        return True, f"repo-local Gemini env already present at {PROJECT_ENV_PATH} via {existing_name}"

    if PROJECT_ENV_PATH.exists():
        backup_once(PROJECT_ENV_PATH)
    write_dotenv(PROJECT_ENV_PATH, key_name, key_value)
    return True, f"synced repo-local Gemini env at {PROJECT_ENV_PATH} from {source}"


def main() -> int:
    args = parse_args()
    backup_once(SETTINGS_PATH)
    payload = load_json(SETTINGS_PATH)
    auth = payload.setdefault("security", {}).setdefault("auth", {})
    auth["selectedType"] = args.mode
    write_json(SETTINGS_PATH, payload)

    print(f"updated {SETTINGS_PATH}")
    if BACKUP_DIR.exists():
        print(f"backup {BACKUP_DIR}")

    sources = key_sources()
    if args.mode == "gemini-api-key":
        invalid_sources = invalid_key_sources()
        if invalid_sources:
            print("warning Gemini API key material is invalid or placeholder in " + ", ".join(invalid_sources))
            print(f"fix replace it with your real Google AI Studio key in {PROJECT_ENV_PATH} or {HOME_ENV_PATH}")
        elif sources:
            print("ready gemini-api-key via " + ", ".join(sources))
            if PROJECT_DOTENV_PATH.exists():
                synced, detail = sync_project_env()
                print(detail)
                if not synced:
                    print(
                        "warning this repo has its own .env, so Gemini may ignore the home-level key until a repo-local .gemini/.env exists"
                    )
        else:
            print("warning no GEMINI_API_KEY or GOOGLE_API_KEY found in shell or ~/.gemini/.env")
            print(f"next add GEMINI_API_KEY=... to {HOME_ENV_PATH} or export it in your shell")
    else:
        print("selected oauth-personal")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
