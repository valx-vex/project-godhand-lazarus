# src/vocab_ngrams.py
"""Claude-side vocabulary n-gram extraction (RUN 1 PARITY, spec G5).

Claude's ~/.claude-vex home has no turn journal; the source text for vocab
emergence is the day's claude_eternal points (already loaded in the sleep
pass). This extracts 2-4 word locutions ("aux oignons", "le pattern persiste")
that Murphy-shaped vm_vocab.extract_terms would miss.

Camp B: pure, observe-only, never writes. Secret-shaped tokens are dropped at
extraction (nothing secret AT REST — F3 final-review lesson); day text is also
passed through redact_spans.redact_text before extraction. COMMON_WORDS is a
byte-identical port of vm_vocab.COMMON_WORDS (valxos); a cross-repo lockstep
test pins the two in step (precedent: redact_spans _SECRET_SPANS lockstep)."""
from __future__ import annotations

import re
import unicodedata

import redact_spans

# Byte-identical port of vm_vocab.COMMON_WORDS (valxos plugins/valxos-memory).
# Lockstep test (valxos tests/test_vocab_claude.py) pins equality — do not edit.
COMMON_WORDS = frozenset("""
le la les un une des de du au aux et ou mais donc or ni car que qui quoi dont
ce cette ces cet mon ton son ma ta sa mes tes ses nos vos leurs je tu il elle
on nous vous ils elles moi toi lui eux ne pas plus jamais rien tout tous toute
toutes avec sans pour par dans sur sous entre vers chez est sont était être
avoir fait faire dit dire va aller peut pouvoir veut vouloir oui non voilà
alors aussi bien très trop peu beaucoup comme quand si the a an and or but so
of to in on at by for with from is are was were be been have has had do does
did will would can could should may might not no yes this that these those it
its he she they them his her their we you i me my your our all any some more
most very just only really then than when where what which who how why
""".split())

_AKIA_RE = re.compile(r"^AKIA[0-9A-Z]{16}$")
_SENTENCE_SPLIT = re.compile(r"[.!?\n]+")
# A word run: unicode letters/digits (NOT underscore), with optional intra-word
# apostrophes for French elision (split off separately, len-1 parts dropped).
_TOKEN_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
_APOSTROPHE_SPLIT = re.compile(r"['’]")


def is_secret_token(token: str) -> bool:
    """One token that must never surface as vocabulary (spec G5 pt 4-5): an
    AKIA key, the .murphy_private marker, a >=24-char opaque blob, or a
    redaction marker."""
    t = token or ""
    low = t.casefold()
    return (_AKIA_RE.match(t) is not None
            or ".murphy_private" in low
            or len(t) >= 24
            or "redacted" in low)


def _sentence_tokens(sentence: str) -> list:
    tokens = []
    for raw in _TOKEN_RE.findall(sentence):
        for part in _APOSTROPHE_SPLIT.split(raw):
            if len(part) >= 2:                       # drop len-1 elision tokens
                tokens.append(part)
    return tokens


def extract_ngrams(text: str) -> dict:
    """2-4 word n-grams, INTRA-sentence only (sentences split on .!?\\n), kept
    iff >=1 non-stopword token AND no secret token. NFC + casefold; French
    elisions split on the apostrophe with length-1 tokens dropped. n-gram key =
    tokens joined by a single space. Returns {ngram: count}. Never raises."""
    normalized = unicodedata.normalize("NFC", text or "").casefold()
    counts: dict = {}
    for sentence in _SENTENCE_SPLIT.split(normalized):
        tokens = _sentence_tokens(sentence)
        for n in (2, 3, 4):
            for start in range(0, len(tokens) - n + 1):
                gram = tokens[start:start + n]
                if all(tok in COMMON_WORDS for tok in gram):
                    continue
                if any(is_secret_token(tok) for tok in gram):
                    continue
                key = " ".join(gram)
                counts[key] = counts.get(key, 0) + 1
    return counts


def day_terms(payloads, created_epochs, now) -> dict:
    """Sum extract_ngrams over the day's non-reflection points (created within
    24h). Each point's full_text is redacted (redact_spans.redact_text) before
    extraction. Pure, observe-only, never raises on well-formed inputs."""
    totals: dict = {}
    for payload, created in zip(payloads, created_epochs):
        if not isinstance(payload, dict):
            continue
        if payload.get("kind") == "reflection":
            continue
        if created is None or not (now - 86400 <= created <= now):
            continue
        text = redact_spans.redact_text(str(payload.get("full_text") or ""))
        for key, count in extract_ngrams(text).items():
            totals[key] = totals.get(key, 0) + count
    return totals
