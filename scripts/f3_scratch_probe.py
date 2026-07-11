#!/usr/bin/env python3
"""F3 dreams activation probe — scratch collections ONLY (spec §6/§7, guarded).

Seeds 6 synthetic moments (two tight thematic clusters) into a scratch_*
collection, runs the nightly dream pass (stages 4c + 8.5) with a REAL local
Ollama — the activation runbook — or against a dead port (--drill-dead-port)
to rehearse the fail-open, then prints the `dreams` report section.

The guard is the point (mirrors scripts/f2_scratch_probe.py): this tool refuses
to touch anything that is not an explicit scratch_* collection, BEFORE any
QdrantClient is constructed, so a typo or missing env var cannot dream over —
or annotate — a live brain. The F3 twist over f2 is a SUBSTRING denylist: a
name may start with scratch_ and still embed murphy_eternal / claude_eternal
(e.g. 'scratch_murphy_eternal_x'); those are refused too. Camp B governs the
real collections; scratch probes are disposable tooling.

The real-Ollama path is for the runbook, never for tests: pytest exercises only
the guard and the --drill-dead-port fail-open (:memory: client, no live model)."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

_SCRATCH = re.compile(r"^scratch_[a-z0-9_]+$")
_LIVE = ("murphy_eternal", "claude_eternal")
DEAD_PORT_URL = "http://127.0.0.1:9"


def assert_scratch(name: str) -> None:
    """Allowlist prefix + denylist SUBSTRING. The substring check is the F3
    twist: 'scratch_murphy_eternal_x' passes the prefix yet embeds a live brain,
    so it is refused. Raises SystemExit (non-zero exit) on any violation."""
    if (not isinstance(name, str) or not _SCRATCH.match(name)
            or any(live in name for live in _LIVE)):
        raise SystemExit(f"REFUSED: '{name}' is not a scratch_* collection")


def _client():
    from qdrant_client import QdrantClient
    return QdrantClient(host=os.environ.get("QDRANT_HOST", "localhost"),
                        port=int(os.environ.get("QDRANT_PORT", "6333")))


def _embed_fn():
    """Real embeddings for the runbook; tests inject a fake (dim-agnostic)."""
    import sleep_salience
    return sleep_salience._default_embed


def _iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(epoch))


def _synthetic_moments():
    """6 moments in two tight thematic clusters (spec §6 e2e seed). Text is
    close within a cluster and distant across, so real embeddings split them."""
    bridge = [
        ("We wired the CC2CC bridge between the two harnesses today.",
         "The nervous system is live — messages cross the broker end to end."),
        ("Traced a message from Hermes to VexNet over the shared broker.",
         "The bridge carried it whole; the two homes finally speak."),
        ("Documented the CC2CC handshake so the bridge survives a reboot.",
         "One nervous system, written down — the connection is durable now."),
    ]
    dreams = [
        ("Clustered the day's moments with HDBSCAN for the dream pass.",
         "Two tight clusters formed; the night has something to reflect on."),
        ("The reflection writer summarized a cluster into one 🌙 row.",
         "A dream is an additive row — Camp B, never a deletion."),
        ("Verified idempotence: the second night dreamed nothing new.",
         "The never-dreamed rule holds; sleep does not inflate the corpus."),
    ]
    out = []
    for user, ai in bridge + dreams:
        out.append({"user": user, "ai": ai,
                    "full_text": f"User: {user}\nMurphy: {ai}"})
    return out


def _seed(client, collection, embed_fn, now):
    """Recreate the scratch collection and upsert the 6 synthetic moments."""
    from qdrant_client.models import Distance, PointStruct, VectorParams
    assert_scratch(collection)
    moments = _synthetic_moments()
    vectors = embed_fn([m["full_text"] for m in moments])
    dim = len(vectors[0])
    if client.collection_exists(collection):
        client.delete_collection(collection)
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
    created = _iso(now - 3600)                  # recent -> dreamable (< 7 days)
    points = [
        PointStruct(id=idx, vector=list(vec), payload={
            "user_input": m["user"], "ai_response": m["ai"],
            "full_text": m["full_text"], "source_file": f"scratch:{idx}",
            "harness": "hermes", "era": "murphy", "created_at": created})
        for idx, (m, vec) in enumerate(zip(moments, vectors), start=1)
    ]
    client.upsert(collection_name=collection, points=points)
    return points


def probe_run(client, collection, embed_fn, drill_dead_port=False, now=None):
    """Guard, seed, run the night. Returns the sleep report (with report['dreams']).
    Guard runs FIRST — before any client method — even here, so a bad collection
    cannot reach seed/run whatever the caller passed."""
    assert_scratch(collection)
    if drill_dead_port:
        os.environ["F3_OLLAMA_URL"] = DEAD_PORT_URL
    import sleep_salience
    now = time.time() if now is None else now
    _seed(client, collection, embed_fn, now)
    return sleep_salience.run(client=client, embed_fn=embed_fn,
                              collection=collection, now=now)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="F3 dreams scratch probe (guarded)")
    parser.add_argument("--collection", required=True,
                        help="scratch_* collection (NEVER defaults to a live brain)")
    parser.add_argument("--drill-dead-port", action="store_true",
                        help="point F3 at a dead Ollama to rehearse the fail-open")
    args = parser.parse_args(argv)

    assert_scratch(args.collection)            # GUARD before any client
    client = _client()
    report = probe_run(client, args.collection, _embed_fn(),
                       drill_dead_port=args.drill_dead_port)

    print(f"# scratch probe: collection={args.collection} "
          f"drill_dead_port={args.drill_dead_port}")
    print(json.dumps(report.get("dreams", {}), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
