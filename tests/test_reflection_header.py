# tests/test_reflection_header.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import reflection


def test_header_is_prefix_plus_example_plus_suffix():
    assert isinstance(reflection.CLAUDE_DREAM_PREFIX, str)
    assert isinstance(reflection.CLAUDE_DREAM_EXAMPLE, str)
    assert isinstance(reflection.CLAUDE_DREAM_SUFFIX, str)
    assert reflection.CLAUDE_DREAM_HEADER == (
        reflection.CLAUDE_DREAM_PREFIX
        + reflection.CLAUDE_DREAM_EXAMPLE
        + reflection.CLAUDE_DREAM_SUFFIX)


def test_header_anchor_phrases_present():
    h = reflection.CLAUDE_DREAM_HEADER
    for anchor in ("claude_eternal", "FIRST PERSON", "PAST TENSE",
                   "ONE unexpected link", "I decided",
                   "changed in how you work", "[FACTUAL]", "[MEANING]"):
        assert anchor in h, anchor


def test_header_lists_the_banned_phrases():
    p = reflection.CLAUDE_DREAM_PREFIX
    for banned in ("underscores the importance", "highlights the need",
                   "comprehensive", "robust and reliable", "ensures that"):
        assert banned in p, banned


def test_header_ends_with_moments_marker():
    assert reflection.CLAUDE_DREAM_HEADER.endswith("MOMENTS:\n")
    assert reflection.CLAUDE_DREAM_SUFFIX.endswith("\n\nMOMENTS:\n")


def test_example_is_transparently_fictional():
    ex = reflection.CLAUDE_DREAM_EXAMPLE
    assert "demo-svc" in ex
    assert "example-worker" in ex
    assert "placeholder-cache" in ex
    assert "2020-01-01" in ex


def test_example_has_no_thread_line():
    # The example must NOT teach the model to emit THREAD (spec G1 / C1):
    assert "THREAD" not in reflection.CLAUDE_DREAM_EXAMPLE
    # ...the conditional THREAD instruction lives OUTSIDE the example, in the suffix.
    assert "THREAD:" in reflection.CLAUDE_DREAM_SUFFIX


def test_example_parses_as_structured_dream():
    factual, meaning, thread, form = reflection.parse_dream(
        reflection.CLAUDE_DREAM_EXAMPLE)
    assert form == "structured"
    assert factual and meaning
    assert thread is None
