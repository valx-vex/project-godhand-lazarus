# src/redact_spans.py
"""F3-boundary redaction (spec v2.1 §3.8, triage T1).

Session-turn ingestion is RAW (ingest_hermes/_claude_vex carry no redaction);
L3/vm_deny covers only the tool-capture path. F3 therefore redacts at ITS OWN
boundaries: every text entering an LLM prompt and every LLM output persisted
or rendered. Patterns are a byte-in-lockstep mirror of
ingest_tool_digest._SECRET_SPANS / vm_deny (T13 rule — lockstep test pins them).
Never deletes points, never gates raw-memory writes."""
from __future__ import annotations

import re

PRIVATE_TOKEN = ".murphy_private"
SECRET_SPANS = [
    re.compile(r"-----BEGIN[A-Z ]*KEY-----.*?-----END[A-Z ]*KEY-----", re.DOTALL),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)\bapi[_-]?key\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+]{8,}['\"]?"),
    re.compile(r"(?i)\bpassword\b\s*[:=]\s*['\"]?[^\s'\"]{4,}['\"]?"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"),
]


def redact_text(text: str) -> str:
    if not text:
        return text
    for pattern in SECRET_SPANS:
        text = pattern.sub("<REDACTED: secret_content>", text)
    return text.replace(PRIVATE_TOKEN, "<redacted:murphy_private>")


def contains_secret(text: str) -> bool:
    if not text:
        return False
    if PRIVATE_TOKEN in text:
        return True
    return any(pattern.search(text) for pattern in SECRET_SPANS)


def is_secret_term(term: str) -> bool:
    return contains_secret(term or "")
