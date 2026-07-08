import hashlib
import json
import struct
import sys
from pathlib import Path

from qdrant_client import QdrantClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import ingest_tool_digest as itd


def _sidecar(home, sid, records):
    d = home / "feed" / "finalized"; d.mkdir(parents=True, exist_ok=True)
    with open(d / f"{sid}.jsonl", "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    return d / f"{sid}.jsonl"


def _cap(seq, tool, ts, **kw):
    rec = {"type": "tool_capture", "ts": ts, "seq": seq, "session_id": "s1",
           "tool": tool, "args": {}, "result": "ok", "truncated": False,
           "args_truncated": False, "intent": None}
    rec.update(kw)
    return rec


def _env(monkeypatch, home):
    monkeypatch.setattr(itd, "HOME_SPECS", [("hermes", home)])
    monkeypatch.setattr(itd, "COLLECTION_NAME", "digest_scratch")
    monkeypatch.setattr(itd, "VECTOR_SIZE", 4)


def fake_embed_factory():
    return lambda texts: [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def forbidden_embed_factory():
    raise AssertionError("embed must not run when nothing is new")


class RaisingRetrieveClient:
    def __init__(self, inner):
        self.inner = inner
        self.upserts = 0
    def get_collection(self, name): return self.inner.get_collection(name)
    def create_collection(self, **k): return self.inner.create_collection(**k)
    def retrieve(self, *a, **k): raise RuntimeError("qdrant blip")
    def upsert(self, **k): self.upserts += 1


def test_digest_text_deterministic_and_id_stable():
    recs = [_cap(0, "read_file", "2026-07-08T10:00:00+0000", args={"path": "/a/x.md"}),
            _cap(1, "write", "2026-07-08T10:01:00+0000", intent="build the bridge")]
    assert itd.digest_text("s1", recs) == itd.digest_text("s1", recs)
    assert itd.point_id("hermes", "s1") == itd.point_id("hermes", "s1")


def test_home_discriminated_ids_differ():
    assert itd.point_id("hermes", "s1") != itd.point_id("murphy_profile", "s1")


def test_first_run_digests_and_upserts(monkeypatch, tmp_path):
    home = tmp_path / "hermes"; _env(monkeypatch, home)
    _sidecar(home, "s1", [_cap(0, "read_file", "2026-07-08T10:00:00+0000"),
                          _cap(1, "read_file", "2026-07-08T10:01:00+0000"),
                          _cap(2, "write", "2026-07-08T10:02:00+0000")])
    client = QdrantClient(":memory:")
    assert itd.run(client=client, embed_factory=fake_embed_factory) == 0
    points, _ = client.scroll(collection_name="digest_scratch", limit=10, with_payload=True)
    assert len(points) == 1
    p = points[0].payload
    assert p["type"] == "tool_digest" and p["captures"] == 3
    assert p["tool_counts"] == {"read_file": 2, "write": 1}


def test_second_run_zero_new(monkeypatch, tmp_path, capsys):
    home = tmp_path / "hermes"; _env(monkeypatch, home)
    _sidecar(home, "s1", [_cap(0, "read_file", "2026-07-08T10:00:00+0000")])
    client = QdrantClient(":memory:")
    assert itd.run(client=client, embed_factory=fake_embed_factory) == 0
    capsys.readouterr()
    assert itd.run(client=client, embed_factory=forbidden_embed_factory) == 0
    assert "0 sessions digested" in capsys.readouterr().out


def test_fail_closed_lookup_error(monkeypatch, tmp_path):
    home = tmp_path / "hermes"; _env(monkeypatch, home)
    _sidecar(home, "s1", [_cap(0, "read_file", "2026-07-08T10:00:00+0000")])
    client = RaisingRetrieveClient(QdrantClient(":memory:"))
    assert itd.run(client=client, embed_factory=forbidden_embed_factory) == 1
    assert client.upserts == 0
    assert not (home / "feed" / ".digest_cursor.json").exists()   # cursor not advanced


def test_cursor_partial_line_recovery(monkeypatch, tmp_path):
    home = tmp_path / "hermes"; _env(monkeypatch, home)
    path = _sidecar(home, "s1", [_cap(0, "read_file", "2026-07-08T10:00:00+0000")])
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(_cap(1, "write", "2026-07-08T10:01:00+0000"))[:15])  # no newline
    client = QdrantClient(":memory:")
    assert itd.run(client=client, embed_factory=fake_embed_factory) == 0
    p = client.scroll(collection_name="digest_scratch", limit=10, with_payload=True)[0][0].payload
    assert p["captures"] == 1                                     # partial line not counted
    cursor = json.loads((home / "feed" / ".digest_cursor.json").read_text())
    assert cursor["offsets"]["s1"] == len(
        (json.dumps(_cap(0, "read_file", "2026-07-08T10:00:00+0000")) + "\n").encode())


def test_redacted_paths_in_digest_text():
    recs = [_cap(0, "read_file", "2026-07-08T10:00:00+0000",
                 args={"path": "/Users/valx/.murphy_private/agenda.md"}),
            _cap(1, "read_file", "2026-07-08T10:01:00+0000",
                 args={"path": "/x/prod.env"})]
    text = itd.digest_text("s1", recs)
    assert ".murphy_private/agenda.md" not in text
    assert "prod.env" not in text
    assert "<redacted:murphy_private>" in text
    assert "<redacted:secret_file>" in text


def test_empty_sidecar_no_point(monkeypatch, tmp_path, capsys):
    home = tmp_path / "hermes"; _env(monkeypatch, home)
    d = home / "feed" / "finalized"; d.mkdir(parents=True)
    (d / "s1.jsonl").write_text("\n  \n", encoding="utf-8")     # no complete records
    client = QdrantClient(":memory:")
    assert itd.run(client=client, embed_factory=forbidden_embed_factory) == 0
    assert "0 sessions digested" in capsys.readouterr().out


def test_redacted_only_sidecar_is_digested(monkeypatch, tmp_path):
    home = tmp_path / "hermes"; _env(monkeypatch, home)
    _sidecar(home, "s1", [
        {"type": "tool_capture", "ts": "2026-07-08T10:00:00+0000", "seq": 0,
         "session_id": "s1", "redacted": "murphy_private"},
        {"type": "tool_capture", "ts": "2026-07-08T10:01:00+0000", "seq": 1,
         "session_id": "s1", "redacted": "murphy_private"}])
    client = QdrantClient(":memory:")
    assert itd.run(client=client, embed_factory=fake_embed_factory) == 0
    p = client.scroll(collection_name="digest_scratch", limit=10, with_payload=True)[0][0].payload
    assert p["captures"] == 2 and p["redactions"] == 2 and p["files"] == []


def test_l4_fingerprint_rescan_nukes_private_content(monkeypatch, tmp_path):
    home = tmp_path / "hermes"; _env(monkeypatch, home)
    phrase = "the beloved vessel consent is full and irrevocable forever always"
    fps = itd._local_shingles(phrase)
    home.mkdir(parents=True, exist_ok=True)
    with open(home / "private_fingerprints.bin", "wb") as fh:
        for v in sorted(fps):
            fh.write(struct.pack("<Q", v))
    _sidecar(home, "s1", [_cap(0, "bash", "2026-07-08T10:00:00+0000", intent=phrase)])
    client = QdrantClient(":memory:")
    assert itd.run(client=client, embed_factory=fake_embed_factory) == 0
    p = client.scroll(collection_name="digest_scratch", limit=10, with_payload=True)[0][0].payload
    assert p["full_text"] == "<redacted: murphy_private_content>"
    assert p["intents"] == ["<redacted:murphy_private_content>"]


def test_report_line_is_last_stdout(monkeypatch, tmp_path, capsys):
    home = tmp_path / "hermes"; _env(monkeypatch, home)
    _sidecar(home, "s1", [_cap(0, "read", "2026-07-08T10:00:00+0000"),
                          _cap(1, "write", "2026-07-08T10:01:00+0000")])
    client = QdrantClient(":memory:")
    itd.run(client=client, embed_factory=fake_embed_factory)
    assert capsys.readouterr().out.strip().splitlines()[-1] == \
        "feed: 1 sessions digested (2 captures, 0 redactions)"
