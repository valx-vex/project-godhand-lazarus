from __future__ import annotations

import os
from pathlib import Path


MURPHY_ERAS = (
    "nexus",
    "mother",
    "vex-data-slayer",
    "vex-murphy",
    "murphy",
    "daddy",
)


def normalize_murphy_era(value: str | None, default: str = "murphy") -> str:
    era = (value or "").strip().lower().replace("_", "-")
    return era if era in MURPHY_ERAS else default


def infer_murphy_era(source_file: str | Path | None, default: str = "murphy") -> str:
    haystack = str(source_file or "").lower().replace("_", "-")
    for era in MURPHY_ERAS:
        if era in haystack:
            return era
    return default


def configured_murphy_era(source_file: str | Path | None, default: str = "murphy") -> str:
    configured = os.environ.get("LAZARUS_MURPHY_ERA") or os.environ.get("LAZARUS_ERA")
    if configured:
        return normalize_murphy_era(configured, default=default)
    return infer_murphy_era(source_file, default=default)
