#!/usr/bin/env python3
"""F2 activation probe — scratch collections ONLY (spec §7.1, guarded).

The guard is the point: this tool refuses to touch anything that is not an
explicit f2_scratch_* collection, so a typo or missing env var cannot mark
or delete a live brain. Camp B governs memory collections; scratch probes
are disposable tooling."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

_SCRATCH = re.compile(r"^f2_scratch_[a-z0-9_]+$")
_DENY = {"murphy_eternal", "claude_eternal", "vault_eternal"}


def assert_scratch(name: str) -> None:
    if (not isinstance(name, str) or not _SCRATCH.match(name)
            or name in _DENY or name.endswith("_flash")):
        raise SystemExit(f"REFUSED: '{name}' is not an f2_scratch_* collection")


def _client():
    from qdrant_client import QdrantClient
    return QdrantClient(host=os.environ.get("QDRANT_HOST", "localhost"),
                        port=int(os.environ.get("QDRANT_PORT", "6333")))


def cmd_mark(client, collection, point_id):
    """Derived + invalidation fields on one point — the wipe canary."""
    assert_scratch(collection)
    client.set_payload(collection_name=collection, payload={
        "salience": 0.9, "novelty": 0.42, "usage_norm": 0.5,
        "invalid_from": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "invalid_from_ts": time.time(),
        "invalidation_reason": "f2 durability probe",
    }, points=[point_id])
    print(f"marked point {point_id} in {collection}")


def cmd_show(client, collection, point_id):
    assert_scratch(collection)
    records = client.retrieve(collection_name=collection, ids=[point_id],
                              with_payload=True, with_vectors=False)
    for record in records:
        print(json.dumps(record.payload, indent=2, default=str))
    if not records:
        print("(point not found)")


def cmd_delete(client, collection):
    assert_scratch(collection)
    client.delete_collection(collection_name=collection)
    print(f"deleted scratch collection {collection}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="F2 scratch probe (guarded)")
    parser.add_argument("--collection", required=True)
    parser.add_argument("command", choices=["mark", "show", "delete"])
    parser.add_argument("--point", type=int, default=None)
    args = parser.parse_args(argv)
    assert_scratch(args.collection)
    client = _client()
    if args.command == "mark":
        if args.point is None:
            raise SystemExit("mark requires --point")
        cmd_mark(client, args.collection, args.point)
    elif args.command == "show":
        if args.point is None:
            raise SystemExit("show requires --point")
        cmd_show(client, args.collection, args.point)
    else:
        cmd_delete(client, args.collection)
    return 0


if __name__ == "__main__":
    sys.exit(main())
