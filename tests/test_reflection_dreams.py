# tests/test_reflection_dreams.py
import sys
from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import reflection
import sleep_salience
from f3_fakes import FakeOllama, fake_embed

NOW = 1783500000.0
GOOD_DREAM = ("[FACTUAL] Murphy worked with beloved on VALXOS.\n"
              "[MEANING] The house is love made visible.\nTHREAD: cathedral")


def _client(points):
    c = QdrantClient(":memory:")
    c.create_collection("scratch_f3",
                        vectors_config=VectorParams(size=4, distance=Distance.COSINE))
    if points:
        c.upsert(collection_name="scratch_f3", points=points)
    return c


def _pt(pid, vec, importance=8, **extra):
    payload = {"user_input": f"u{pid}", "ai_response": f"a{pid}",
               "full_text": f"User: u{pid}\nMurphy: a{pid}",
               "source_file": f"s{pid}",
               "created_at": "2026-07-11T01:00:00+0200",
               "importance": importance}
    payload.update(extra)
    return PointStruct(id=pid, vector=vec, payload=payload)


def _cluster_points():
    return [_pt(1, [1.0, 0.0, 0.0, 0.0]), _pt(2, [0.99, 0.01, 0.0, 0.0]),
            _pt(3, [0.98, 0.02, 0.0, 0.0])]


def _run(client, ollama, monkeypatch=None):
    return sleep_salience.run(client=client, embed_fn=fake_embed, now=NOW,
                              collection="scratch_f3", ollama_client=ollama)


def test_parse_dream_structured_and_thread():
    factual, meaning, thread, form = reflection.parse_dream(GOOD_DREAM)
    assert factual.startswith("Murphy worked")
    assert meaning.startswith("The house")
    assert thread == "cathedral" and form == "structured"


def test_parse_dream_freeform_accepted():
    factual, meaning, thread, form = reflection.parse_dream("just a vrille of pure Murphy")
    assert form == "freeform" and factual == "" and "vrille" in meaning


def test_dream_written_with_moon_sources_and_summarized_by():
    client = _client(_cluster_points())
    ollama = FakeOllama(responses=[GOOD_DREAM])
    report = _run(client, ollama)
    dreams = report["dreams"]
    assert dreams["written"] == 1
    rid = dreams["items"][0]["id"]
    stored = client.retrieve("scratch_f3", ids=[rid], with_payload=True)[0]
    assert stored.payload["kind"] == "reflection"
    assert stored.payload["user_input"].startswith("🌙 [FACTUAL]")
    assert sorted(stored.payload["source_ids"]) == [1, 2, 3]
    assert stored.payload["thread"] == "cathedral"
    for member_id in (1, 2, 3):
        member = client.retrieve("scratch_f3", ids=[member_id], with_payload=True)[0]
        assert member.payload["summarized_by"] == rid


def test_members_untouched_beyond_derived_fields_camp_b():
    client = _client(_cluster_points())
    before = {p.id: dict(p.payload) for p in
              client.retrieve("scratch_f3", ids=[1, 2, 3], with_payload=True)}
    _run(client, FakeOllama(responses=[GOOD_DREAM]))
    after = {p.id: dict(p.payload) for p in
             client.retrieve("scratch_f3", ids=[1, 2, 3], with_payload=True)}
    derived = {"summarized_by", "novelty", "near_duplicate_of", "salience",
               "salience_components", "salience_computed_at"}
    for pid in (1, 2, 3):
        for key, value in before[pid].items():
            if key not in derived:
                assert after[pid][key] == value


def test_second_run_writes_nothing_and_calls_no_llm():
    client = _client(_cluster_points())
    _run(client, FakeOllama(responses=[GOOD_DREAM]))
    ollama2 = FakeOllama(responses=[GOOD_DREAM])
    report2 = _run(client, ollama2)
    assert report2["dreams"]["written"] == 0
    dream_calls = [c for c in ollama2.calls if "FACTUAL" in str(c["prompt"])]
    assert dream_calls == []               # never-dreamed rule: no cluster qualifies


def test_llm_down_dreams_skipped_visibly():
    client = _client(_cluster_points())
    report = _run(client, FakeOllama(fail=True))
    assert report["dreams"]["llm_unavailable"] is True
    assert report["dreams"]["written"] == 0


def test_dream_output_redacted_before_persist():
    leak = "[FACTUAL] key AKIAABCDEFGHIJKLMNOP seen.\n[MEANING] oops."
    client = _client(_cluster_points())
    report = _run(client, FakeOllama(responses=[leak]))
    rid = report["dreams"]["items"][0]["id"]
    stored = client.retrieve("scratch_f3", ids=[rid], with_payload=True)[0]
    assert "AKIA" not in stored.payload["full_text"]


def test_sacred_moment_gets_pinned_dedicated_dream():
    pts = [_pt(1, [1.0, 0.0, 0.0, 0.0], importance=10)]
    client = _client(pts)
    report = _run(client, FakeOllama(responses=[GOOD_DREAM]))
    assert report["dreams"]["sacred_written"] == 1
    rid = report["dreams"]["items"][0]["id"]
    stored = client.retrieve("scratch_f3", ids=[rid], with_payload=True)[0]
    assert stored.payload["salience_pinned"] is True
    assert stored.payload["sacred"] is True


def test_skip_lookup_failure_aborts_without_writes(monkeypatch):
    client = _client(_cluster_points())
    def bomb(*a, **k):
        raise reflection.SkipLookupError("down")
    monkeypatch.setattr(reflection, "existing_ids", bomb)
    report = _run(client, FakeOllama(responses=[GOOD_DREAM]))
    assert report["dreams"]["aborted_skip_lookup"] is True
    assert report["dreams"]["written"] == 0


def test_dream_pass_crash_degrades_to_error_line(monkeypatch):
    client = _client(_cluster_points())
    monkeypatch.setattr(reflection, "cluster_corpus",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("degenerate")))
    report = _run(client, FakeOllama(responses=[GOOD_DREAM]))
    assert report is not None
    assert report["dreams"]["error"] is not None
    assert report["dreams"]["written"] == 0


def test_promote_to_pin_candidates_reported():
    pts = [_pt(1, [1.0, 0.0, 0.0, 0.0], importance=9)]
    client = _client(pts)
    report = _run(client, FakeOllama(responses=[GOOD_DREAM]))
    assert report["dreams"]["promote_to_pin"] == [
        {"id": 1, "importance": 9, "preview": "u1"}]


def test_ranking_multiplier_untouched_by_importance():
    import salience
    payload = {"importance": 10, "salience": 0.5,
               "salience_computed_at": "2026-07-11T01:00:00+0200"}
    with_imp = salience.multiplier(payload, now_epoch=NOW)
    del payload["importance"]
    without = salience.multiplier(payload, now_epoch=NOW)
    assert with_imp == without             # observe-only, pinned


def test_member_block_caps_orders_by_importance_and_reports_omitted():
    payloads = [{"full_text": f"t{i}", "importance": i, "created_at": "d"}
                for i in range(14)]
    block, omitted = reflection._member_block(payloads, list(range(14)))
    assert omitted == 2
    assert "2 more moments omitted" in block
    assert block.index("t13") < block.index("t2")   # importance desc (spec §3.3)


def test_dry_run_skips_f3_writes():
    """spec §6 'dry-run n'écrit rien' — stages 4c AND 8.5 both guarded."""
    client = _client(_cluster_points())
    ollama = FakeOllama(responses=[GOOD_DREAM])
    report = sleep_salience.run(client=client, embed_fn=fake_embed, now=NOW,
                                collection="scratch_f3", dry_run=True,
                                ollama_client=ollama)
    assert ollama.calls == []
    assert "dreams" not in report
    rows, _ = client.scroll("scratch_f3", limit=100, with_payload=True)
    assert all(r.payload.get("kind") != "reflection" for r in rows)


def test_parse_dream_midbody_thread_preserves_following_content():
    # RED on CURRENT code: ^THREAD: (MULTILINE) truncates at the mid-body THREAD
    # line, dropping everything after it — the [MEANING] section is lost and the
    # dream degrades to freeform. New semantics: mid-body THREAD is NOT a tail,
    # nothing is truncated, the structured parse survives with all content.
    dream = ("[FACTUAL] I shipped the parser.\n"
             "THREAD: parser\n"
             "[MEANING] This matters because the parser now handles the tail case.")
    factual, meaning, thread, form = reflection.parse_dream(dream)
    assert form == "structured"
    combined = factual + " " + meaning
    assert "This matters because the parser now handles the tail case." in combined


def test_parse_dream_strips_inline_tail_thread():
    # Murphy's real run-1 shape: a non-anchored "THREAD: x" at the very end of
    # the text. The old ^THREAD: (line-anchored) missed it; the label leaked into
    # the meaning. New: an inline THREAD within the final 80 chars is stripped.
    dream = ("[FACTUAL] Murphy woke the bridge.\n"
             "[MEANING] The connection held through the night. THREAD: x")
    factual, meaning, thread, form = reflection.parse_dream(dream)
    assert form == "structured"
    assert thread == "x"
    assert "THREAD" not in meaning
    assert meaning.startswith("The connection held")


def test_parse_dream_midsentence_thread_not_consumed():
    # Negative: THREAD quoted mid-sentence (far from the tail) is NOT consumed.
    dream = ("[FACTUAL] We shipped the flame.\n"
             "[MEANING] I noted that a THREAD: label is only ever meant for "
             "prior-dream references and then kept on writing about the register "
             "metrics for the rest of the long evening.")
    factual, meaning, thread, form = reflection.parse_dream(dream)
    assert thread is None
    assert "THREAD: label" in meaning
    assert form == "structured"


def test_parse_dream_thread_label_still_capped_at_60():
    # Cap 60 chars unchanged (Q2). A THREAD on its own last line is always tail.
    dream = "[FACTUAL] a.\n[MEANING] b.\nTHREAD: " + ("z" * 100)
    _, _, thread, _ = reflection.parse_dream(dream)
    assert thread == "z" * 60
