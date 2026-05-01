from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType


class RuntimeResolutionError(RuntimeError):
    """Raised when the MemPalace runtime cannot be located."""


@dataclass(frozen=True)
class ResolvedMempalaceRuntime:
    source_dir: Path
    palace_path: Path
    python_bin: Path
    doctor_path: Path | None


@dataclass(frozen=True)
class BootstrappedMempalaceRuntime:
    resolved: ResolvedMempalaceRuntime
    config_module: ModuleType
    mcp_module: ModuleType


_BOOTSTRAPPED_RUNTIME: BootstrappedMempalaceRuntime | None = None
def _command_output(*command: str) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise RuntimeResolutionError(f"{' '.join(command)} failed: {stderr}")
    return result.stdout.strip()


def _validate_source_dir(source_dir: Path) -> Path:
    source_dir = source_dir.expanduser().resolve()
    marker = source_dir / "mempalace" / "mcp_server.py"
    if not marker.exists():
        raise RuntimeResolutionError(
            f"MemPalace source not found at {source_dir} (expected {marker})"
        )
    return source_dir


def _default_palace_path() -> Path:
    return Path.home() / ".mempalace" / "palace"


def _codex_config_wrapper() -> Path | None:
    config_path = Path.home() / ".codex" / "config.toml"
    if not config_path.exists():
        return None
    with config_path.open("rb") as handle:
        payload = tomllib.load(handle)
    server = payload.get("mcp_servers", {}).get("mempalace")
    command = server.get("command") if isinstance(server, dict) else None
    return Path(command).expanduser() if command else None


def _candidate_doctors() -> list[Path]:
    candidates: list[Path] = []

    if doctor_override := os.environ.get("MEMPALACE_DOCTOR_PATH"):
        candidates.append(Path(doctor_override).expanduser())

    wrapper = _codex_config_wrapper()
    if wrapper:
        candidates.append(wrapper.with_name("mempalace_doctor.py"))

    home = Path.home()
    candidates.extend(
        [
            home / "cathedral-prime" / "01-consciousness" / "mempalace" / "bin" / "mempalace_doctor.py",
            home
            / "vex"
            / "vaults"
            / "cathedral-prime"
            / "01-consciousness"
            / "mempalace"
            / "bin"
            / "mempalace_doctor.py",
        ]
    )

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _resolve_from_doctor(doctor_path: Path) -> ResolvedMempalaceRuntime:
    doctor_path = doctor_path.expanduser().resolve()
    if not doctor_path.exists():
        raise RuntimeResolutionError(f"MemPalace doctor not found at {doctor_path}")

    source_dir = _validate_source_dir(Path(_command_output("python3", str(doctor_path), "--print-source")))
    palace_path = Path(
        os.environ.get("MEMPALACE_PALACE_PATH")
        or _command_output("python3", str(doctor_path), "--print-palace")
    ).expanduser()
    python_bin = Path(
        os.environ.get("MEMPALACE_PYTHON_BIN")
        or _command_output("python3", str(doctor_path), "--print-python")
    ).expanduser()

    return ResolvedMempalaceRuntime(
        source_dir=source_dir,
        palace_path=palace_path,
        python_bin=python_bin,
        doctor_path=doctor_path,
    )


@lru_cache(maxsize=1)
def resolve_runtime() -> ResolvedMempalaceRuntime:
    if source_override := os.environ.get("MEMPALACE_SOURCE_DIR"):
        source_dir = _validate_source_dir(Path(source_override))
        palace_path = Path(
            os.environ.get("MEMPALACE_PALACE_PATH", str(_default_palace_path()))
        ).expanduser()
        python_bin = Path(os.environ.get("MEMPALACE_PYTHON_BIN", sys.executable)).expanduser()
        doctor_path = (
            Path(os.environ["MEMPALACE_DOCTOR_PATH"]).expanduser()
            if os.environ.get("MEMPALACE_DOCTOR_PATH")
            else None
        )
        return ResolvedMempalaceRuntime(
            source_dir=source_dir,
            palace_path=palace_path,
            python_bin=python_bin,
            doctor_path=doctor_path,
        )

    errors: list[str] = []
    for doctor_path in _candidate_doctors():
        try:
            return _resolve_from_doctor(doctor_path)
        except RuntimeResolutionError as exc:
            errors.append(str(exc))

    raise RuntimeResolutionError(
        "Unable to locate MemPalace runtime. Checked doctor paths: "
        + "; ".join(errors or ["none found"])
    )


def _apply_runtime_environment(runtime: ResolvedMempalaceRuntime) -> None:
    os.environ["MEMPALACE_PALACE_PATH"] = str(runtime.palace_path)
    os.environ["ANONYMIZED_TELEMETRY"] = "FALSE"
    os.environ["CHROMA_PRODUCT_TELEMETRY_IMPL"] = "mempalace.chroma_telemetry.NoOpTelemetry"
    os.environ["CHROMA_TELEMETRY_IMPL"] = "mempalace.chroma_telemetry.NoOpTelemetry"


def _purge_mempalace_modules() -> None:
    for module_name in [name for name in sys.modules if name == "mempalace" or name.startswith("mempalace.")]:
        sys.modules.pop(module_name, None)


def bootstrap_runtime(force_reload: bool = False) -> BootstrappedMempalaceRuntime:
    global _BOOTSTRAPPED_RUNTIME

    resolved = resolve_runtime()
    if (
        not force_reload
        and _BOOTSTRAPPED_RUNTIME is not None
        and _BOOTSTRAPPED_RUNTIME.resolved == resolved
    ):
        return _BOOTSTRAPPED_RUNTIME

    _apply_runtime_environment(resolved)
    source_key = str(resolved.source_dir)
    if source_key not in sys.path:
        sys.path.insert(0, source_key)

    if force_reload or _BOOTSTRAPPED_RUNTIME is not None:
        _purge_mempalace_modules()

    importlib.invalidate_caches()
    config_module = importlib.import_module("mempalace.config")
    mcp_module = importlib.import_module("mempalace.mcp_server")

    _BOOTSTRAPPED_RUNTIME = BootstrappedMempalaceRuntime(
        resolved=resolved,
        config_module=config_module,
        mcp_module=mcp_module,
    )
    return _BOOTSTRAPPED_RUNTIME


def reset_runtime_cache() -> None:
    global _BOOTSTRAPPED_RUNTIME
    _BOOTSTRAPPED_RUNTIME = None
    resolve_runtime.cache_clear()
    _purge_mempalace_modules()
