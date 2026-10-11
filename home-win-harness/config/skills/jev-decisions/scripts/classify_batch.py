#!/usr/bin/env python3
"""
classify_batch.py — Classify a list of items in one batched JEV request.

Usage:
    python3 classify_batch.py --input job.json

job.json shape:
    {
        "items":    ["item 1", "item 2", ...],
        "question": "How would you classify this?",
        "options":  {"optA": "description A", "optB": "description B"}
    }

Output (stdout):
    {"status": "ok", "results": [{"item_index": 0, "choice": "optA", "confidence": 0.9}, ...]}
    {"status": "jev_unavailable"}   — on UNAVAILABLE (fail-open, exit 0)
"""
from __future__ import annotations

import argparse
import json
import sys
import os

# Insert agent-hooks on sys.path so jevlib is importable
_HOOKS = os.path.join(
    os.environ.get("HERMES_HOME", os.path.join(os.path.expanduser("~"), ".hermes")),
    "agent-hooks",
)
if _HOOKS not in sys.path:
    sys.path.insert(0, _HOOKS)

from jevlib.jev_client import UNAVAILABLE, choice, safe_decide  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify items via JEV.")
    parser.add_argument("--input", required=True, help="Path to job JSON file.")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        job = json.load(fh)

    items = job.get("items", [])
    question = job.get("question", "How would you classify this item?")
    options = job.get("options", {})

    if not items or not options:
        print(json.dumps({"status": "ok", "results": []}))
        return

    # Build one batched request with one choice question per item
    questions = {
        "item_%d" % i: choice(
            {"question": question, "item": item},
            options,
        )
        for i, item in enumerate(items)
    }

    answers = safe_decide({"note": "classify_batch", "item_count": len(items)}, questions)

    if answers is UNAVAILABLE:
        print(json.dumps({"status": "jev_unavailable"}))
        return

    results = []
    for i in range(len(items)):
        key = "item_%d" % i
        ans = answers.get(key, {})
        results.append({
            "item_index": i,
            "choice": ans.get("choice"),
            "confidence": ans.get("confidence", 0),
        })

    print(json.dumps({"status": "ok", "results": results}))


if __name__ == "__main__":
    main()
