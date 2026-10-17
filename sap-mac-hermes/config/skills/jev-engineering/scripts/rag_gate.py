#!/usr/bin/env python3
"""
rag_gate.py — Gate RAG retrieved chunks: score relevance to the query.

Usage:
    python3 rag_gate.py --input job.json

job.json shape:
    {
        "query":     "What is the retry policy?",
        "retrieved": ["Chunk about retry...", "Unrelated chunk..."]
    }

Output (stdout):
    {"status": "ok", "results": [{"chunk_index": 0, "relevant_noul": 0.85}, ...]}
    {"status": "jev_unavailable"}
"""
from __future__ import annotations

import argparse
import json
import sys
import os

_HOOKS = os.path.join(
    os.environ.get("HERMES_HOME", os.path.join(os.path.expanduser("~"), ".hermes")),
    "agent-hooks",
)
if _HOOKS not in sys.path:
    sys.path.insert(0, _HOOKS)

from jevlib.jev_client import UNAVAILABLE, noul, safe_decide  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate RAG chunks via JEV.")
    parser.add_argument("--input", required=True, help="Path to job JSON file.")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        job = json.load(fh)

    query = job.get("query", "")
    retrieved = job.get("retrieved", [])

    if not retrieved:
        print(json.dumps({"status": "ok", "results": []}))
        return

    questions = {
        "chunk_%d" % i: noul(
            {"question": "Is this chunk relevant to the query?",
             "query": query,
             "chunk": chunk}
        )
        for i, chunk in enumerate(retrieved)
    }

    answers = safe_decide({"note": "rag_gate", "query": query}, questions)

    if answers is UNAVAILABLE:
        print(json.dumps({"status": "jev_unavailable"}))
        return

    results = []
    for i in range(len(retrieved)):
        key = "chunk_%d" % i
        ans = answers.get(key, {})
        results.append({
            "chunk_index":   i,
            "relevant_noul": ans.get("noul", 0),
        })

    print(json.dumps({"status": "ok", "results": results}))


if __name__ == "__main__":
    main()
