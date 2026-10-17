#!/usr/bin/env python3
"""
halluc_guard.py — Detect hallucinations: verify code/doc claims against sources.

Uses jevlib.decisions.citation_claims under the hood.

Usage:
    python3 halluc_guard.py --input job.json

job.json shape:
    {
        "claims": [
            {"claim": "Function X returns bool", "source": "def X() -> int: ..."},
            ...
        ]
    }

Output (stdout):
    {"status": "ok", "results": [{"index": 0, "verdict": "contradicts", "confidence": 0.9}, ...]}
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

from jevlib.jev_client import UNAVAILABLE  # noqa: E402
from jevlib.decisions import citation_claims  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard against hallucinations via JEV.")
    parser.add_argument("--input", required=True, help="Path to job JSON file.")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        job = json.load(fh)

    claims = job.get("claims", [])

    if not claims:
        print(json.dumps({"status": "ok", "results": []}))
        return

    result = citation_claims(claims)

    if result is UNAVAILABLE:
        print(json.dumps({"status": "jev_unavailable"}))
        return

    results = []
    for i in range(len(claims)):
        entry = result.get(i, {"verdict": "says_nothing", "confidence": 0})
        results.append({
            "index":      i,
            "verdict":    entry.get("verdict", "says_nothing"),
            "confidence": entry.get("confidence", 0),
        })

    print(json.dumps({"status": "ok", "results": results}))


if __name__ == "__main__":
    main()
