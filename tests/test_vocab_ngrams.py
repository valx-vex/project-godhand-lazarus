# tests/test_vocab_ngrams.py
import sys
import time
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import vocab_ngrams
import sleep_salience
from f3_fakes import fake_embed

NOW = 1783500000.0


# ---- extract_ngrams semantics (spec G5 pins) ----

def test_extract_keeps_leading_article_bigram_aux_oignons():
    out = vocab_ngrams.extract_ngrams(
        "Le pattern persiste. Aux oignons pour toujours.")
    assert out.get("aux oignons", 0) >= 1           # article kept glued (>=1 non-stop)
    assert out.get("le pattern persiste", 0) >= 1


def test_extract_ngrams_are_intra_sentence_only():
    # "persiste" (sentence 1) and "aux" (sentence 2) must never combine.
    out = vocab_ngrams.extract_ngrams("Le pattern persiste. Aux oignons.")
    assert all("persiste aux" not in k for k in out)


def test_extract_french_elision_drops_len1_token():
    out = vocab_ngrams.extract_ngrams("J'ai vu l'oignon.")
    assert "vu oignon" in out                        # l' elided -> oignon glues to vu
    assert all("'" not in k for k in out)


def test_extract_drops_ngram_with_24plus_opaque_token():
    blob = "abcdefghijklmnopqrstuvwxyz1234"          # 30 chars, no space
    out = vocab_ngrams.extract_ngrams("token " + blob + " here")
    assert all(blob not in k for k in out)


def test_extract_drops_ngram_with_redacted_marker():
    out = vocab_ngrams.extract_ngrams("the redacted secret here")
    assert all("redacted" not in k for k in out)


def test_is_secret_token_akia_and_clean():
    assert vocab_ngrams.is_secret_token("AKIAABCDEFGHIJKLMNOP") is True
    assert vocab_ngrams.is_secret_token("oignons") is False


def test_common_words_is_frozenset_with_expected_members():
    assert isinstance(vocab_ngrams.COMMON_WORDS, frozenset)
    for w in ("aux", "le", "la", "pour", "the", "and"):
        assert w in vocab_ngrams.COMMON_WORDS


# ---- day_terms window / redaction / reflection-exclusion ----

def _payload(full_text, kind=None):
    p = {"full_text": full_text}
    if kind is not None:
        p["kind"] = kind
    return p


def test_day_terms_excludes_points_older_than_24h():
    payloads = [_payload("Aux oignons pour toujours."),
                _payload("Le vieux code oublie.")]
    epochs = [NOW - 3600, NOW - 200000]              # 1h ago (in), ~55h ago (out)
    out = vocab_ngrams.day_terms(payloads, epochs, NOW)
    assert out.get("aux oignons", 0) >= 1
    assert all("vieux" not in k for k in out)


def test_day_terms_excludes_reflections():
    payloads = [_payload("Aux oignons pour toujours."),
                _payload("Les caches oublies du soir.", kind="reflection")]
    epochs = [NOW - 100, NOW - 100]
    out = vocab_ngrams.day_terms(payloads, epochs, NOW)
    assert out.get("aux oignons", 0) >= 1
    assert all("caches" not in k for k in out)


def test_day_terms_redacts_akia_before_extraction():
    payloads = [_payload("On a vu AKIAABCDEFGHIJKLMNOP hier soir.")]
    epochs = [NOW - 100]
    out = vocab_ngrams.day_terms(payloads, epochs, NOW)
    assert all("akia" not in k.lower() for k in out)


# ---- run() report contract (C2) ----

def _cpt(pid, full_text, created_epoch):
    created_at = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(created_epoch))
    return PointStruct(id=pid, vector=[1.0, 0.0, 0.0, 0.0],
                       payload={"user_input": "u" + str(pid),
                                "ai_response": "a" + str(pid),
                                "full_text": full_text,
                                "source_file": "s" + str(pid),
                                "created_at": created_at})


def _client(name, points):
    c = QdrantClient(":memory:")
    c.create_collection(
        name, vectors_config=VectorParams(size=4, distance=Distance.COSINE))
    if points:
        c.upsert(collection_name=name, points=points)
    return c


def test_run_reports_vocab_terms_for_claude_eternal():
    client = _client("claude_eternal",
                     [_cpt(1, "Aux oignons pour toujours.", NOW - 3600)])
    report = sleep_salience.run(client=client, embed_fn=fake_embed, now=NOW,
                                collection="claude_eternal", dry_run=True)
    assert isinstance(report["vocab_terms"], dict)
    assert report["vocab_terms"].get("aux oignons", 0) >= 1


def test_run_omits_vocab_terms_for_other_collections():
    client = _client("scratch_vocab",
                     [_cpt(1, "Aux oignons pour toujours.", NOW - 3600)])
    report = sleep_salience.run(client=client, embed_fn=fake_embed, now=NOW,
                                collection="scratch_vocab", dry_run=True)
    assert "vocab_terms" not in report
