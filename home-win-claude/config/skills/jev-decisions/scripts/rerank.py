#!/usr/bin/env python
"""
rerank.py — Rerank candidates by relevance to a query via JEV NOUL questions.

Usage:
    python rerank.py --input job.json

job.json shape:
    {
        "query":      "your search query",
        "candidates": ["candidate 1", "candidate 2", ...]
    }

Output (stdout):
    {"status": "ok", "results": [{"candidate": "...", "noul": 0.9}, ...]}  sorted desc by noul
    {"status": "jev_unavailable"}   — on UNAVAILABLE (fail-open, exit 0)
"""
from __future__ import annotations

import argparse
import json
import sys
import os
import pathlib

_HOOKS = os.path.join(os.environ["HERMES_HOME"], "agent-hooks") if os.environ.get("HERMES_HOME") else str(pathlib.Path(__file__).resolve().parents[3] / "agent-hooks")
if _HOOKS not in sys.path:
    sys.path.insert(0, _HOOKS)

from jevlib.jev_client import UNAVAILABLE, noul, safe_decide  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Rerank candidates via JEV.")
    parser.add_argument("--input", required=True, help="Path to job JSON file.")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        job = json.load(fh)

    query = job.get("query", "")
    candidates = job.get("candidates", [])

    if not candidates:
        print(json.dumps({"status": "ok", "results": []}))
        return

    questions = {
        "cand_%d" % i: noul(
            {"question": "Could this candidate answer the query?",
             "query": query,
             "candidate": c}
        )
        for i, c in enumerate(candidates)
    }

    answers = safe_decide({"note": "rerank", "query": query}, questions)

    if answers is UNAVAILABLE:
        print(json.dumps({"status": "jev_unavailable"}))
        return

    scored = []
    for i, c in enumerate(candidates):
        key = "cand_%d" % i
        ans = answers.get(key, {})
        scored.append({"candidate": c, "noul": ans.get("noul", 0)})

    # Sort descending by noul score
    scored.sort(key=lambda x: x["noul"], reverse=True)

    print(json.dumps({"status": "ok", "results": scored}))


if __name__ == "__main__":
    main()
