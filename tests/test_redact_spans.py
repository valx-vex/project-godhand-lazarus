# tests/test_redact_spans.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import redact_spans


def test_redacts_aws_key_span():
    text = "deploy used AKIAABCDEFGHIJKLMNOP for auth"
    out = redact_spans.redact_text(text)
    assert "AKIA" not in out
    assert "<REDACTED: secret_content>" in out


def test_redacts_password_assignment():
    out = redact_spans.redact_text("then password: hunter2 was set")
    assert "hunter2" not in out


def test_redacts_pem_block():
    pem = "-----BEGIN RSA KEY-----\nabc\n-----END RSA KEY-----"
    assert "BEGIN" not in redact_spans.redact_text(pem)


def test_replaces_private_token():
    out = redact_spans.redact_text("see .murphy_private/notes.md")
    assert ".murphy_private" not in out
    assert "<redacted:murphy_private>" in out


def test_clean_text_unchanged():
    text = "Murphy worked with beloved on VALXOS. GAGAGAGA 💚"
    assert redact_spans.redact_text(text) == text


def test_contains_secret():
    assert redact_spans.contains_secret("bearer abcdefgh12345678")
    assert not redact_spans.contains_secret("a quiet evening")


def test_is_secret_term():
    assert redact_spans.is_secret_term("AKIAABCDEFGHIJKLMNOP")
    assert redact_spans.is_secret_term("x.murphy_privatey")
    assert not redact_spans.is_secret_term("GAGAGAGAGA")


def test_lockstep_with_tool_digest_spans():
    import ingest_tool_digest
    ours = [p.pattern for p in redact_spans.SECRET_SPANS]
    theirs = [p.pattern for p in ingest_tool_digest._SECRET_SPANS]
    assert ours == theirs
    assert redact_spans.PRIVATE_TOKEN == ingest_tool_digest._PRIVATE_TOKEN
