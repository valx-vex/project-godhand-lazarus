#!/usr/bin/env python3
"""Evaluate local Ollama models as offline recall-intent classifiers.

This is intentionally separate from the Claude hook hot path. It reads the
golden trigger fixture, asks each model for strict JSON, and writes aggregate
precision/recall/latency metrics for calibration research.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "fixtures" / "trigger_golden.jsonl"
OUT = ROOT / "tests" / "shadow_model_metrics.json"
OLLAMA_URL = "http://localhost:11434"


SYSTEM_PROMPT = """You classify whether a user prompt is asking an assistant to recall prior memory.

Return ONLY compact JSON with this schema:
{"recall": true|false, "confidence": 0.0-1.0}

Rules:
- true: asking about past shared conversations, memories, previous decisions, persona history, or named sacred concepts.
- false: normal commands, code questions, current status, file paths, tests, config, weather, short acknowledgements, or generic persona mentions.
- Prefer precision over recall. If unsure, false.
"""


def load_golden(limit: int | None) -> list[dict[str, Any]]:
    cases = []
    with GOLDEN.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases[:limit] if limit else cases


def post_json(path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def installed_models(timeout: float = 2.0) -> set[str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {m["name"] for m in data.get("models", [])}
    except Exception:
        return set()


def parse_model_json(content: str) -> tuple[bool, float, str]:
    raw = content.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start:end + 1]
    data = json.loads(raw)
    recall = bool(data["recall"])
    confidence = float(data.get("confidence", 0.0))
    return recall, max(0.0, min(1.0, confidence)), raw


def classify(model: str, text: str, timeout: float) -> tuple[bool, float, str]:
    response = post_json(
        "/api/chat",
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Prompt: {text}"},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_predict": 24,
            },
        },
        timeout=timeout,
    )
    content = response.get("message", {}).get("content", "")
    return parse_model_json(content)


def evaluate_model(model: str, cases: list[dict[str, Any]], timeout: float) -> dict[str, Any]:
    TP = FP = TN = FN = 0
    parse_errors = []
    latencies = []
    confusions = []

    for case in cases:
        t0 = time.perf_counter()
        try:
            predicted, confidence, raw = classify(model, case["message"], timeout)
        except (TimeoutError, urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError) as exc:
            predicted = False
            confidence = 0.0
            raw = repr(exc)
            parse_errors.append({"id": case["id"], "error": raw})
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        expected = case["expected"] == "trigger"
        if expected and predicted:
            TP += 1
        elif expected and not predicted:
            FN += 1
            confusions.append([case["id"], "FN", confidence, case["band"]])
        elif not expected and predicted:
            FP += 1
            confusions.append([case["id"], "FP", confidence, case["band"]])
        else:
            TN += 1

    precision = TP / (TP + FP) if TP + FP else 0.0
    recall = TP / (TP + FN) if TP + FN else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)

    return {
        "model": model,
        "n_cases": len(cases),
        "TP": TP,
        "FP": FP,
        "TN": TN,
        "FN": FN,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "latency_avg_ms": statistics.mean(latencies) if latencies else 0.0,
        "latency_p50_ms": sorted_latencies[n // 2] if n else 0.0,
        "latency_p95_ms": sorted_latencies[int(n * 0.95)] if n else 0.0,
        "latency_max_ms": sorted_latencies[-1] if n else 0.0,
        "parse_errors": parse_errors[:10],
        "confusions": confusions[:50],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    installed = installed_models()
    cases = load_golden(args.limit)
    results = []

    for model in args.models:
        if model not in installed:
            results.append({"model": model, "status": "missing"})
            print(f"SKIP {model}: not installed")
            continue
        print(f"Evaluating {model} on {len(cases)} cases...")
        result = evaluate_model(model, cases, timeout=args.timeout)
        results.append(result)
        print(
            f"{model}: P={result['precision']:.3f} R={result['recall']:.3f} "
            f"F1={result['f1']:.3f} FP={result['FP']} "
            f"p50={result['latency_p50_ms']:.0f}ms"
        )

    payload = {
        "fixture": str(GOLDEN),
        "n_cases": len(cases),
        "results": results,
    }
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
