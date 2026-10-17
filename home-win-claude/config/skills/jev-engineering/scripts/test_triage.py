#!/usr/bin/env python
"""
test_triage.py — Triage failing tests: classify as skip, flaky, or investigate.

Usage:
    python test_triage.py --input job.json

job.json shape:
    {
        "tests": [
            {"name": "test_login", "failure": "AssertionError: expected 200 got 401"},
            {"name": "test_flaky_net", "failure": "Timeout after 5s"}
        ]
    }

Output (stdout):
    {"status": "ok", "results": [{"name": "...", "action": "investigate", "confidence": 0.9}, ...]}
    {"status": "jev_unavailable"}
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

from jevlib.jev_client import UNAVAILABLE, choice, safe_decide  # noqa: E402

_ACTION_OPTIONS = {
    "investigate": "Deterministic failure; root cause needs engineering attention.",
    "flaky":       "Non-deterministic or environment-dependent failure; retry.",
    "skip":        "Test is outdated, irrelevant, or intentionally disabled.",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Triage failing tests via JEV.")
    parser.add_argument("--input", required=True, help="Path to job JSON file.")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        job = json.load(fh)

    tests = job.get("tests", [])

    if not tests:
        print(json.dumps({"status": "ok", "results": []}))
        return

    questions = {
        "test_%d" % i: choice(
            {"question": "What action should be taken on this failing test?",
             "name": t.get("name", ""),
             "failure": t.get("failure", "")},
            _ACTION_OPTIONS,
        )
        for i, t in enumerate(tests)
    }

    answers = safe_decide({"note": "test_triage"}, questions)

    if answers is UNAVAILABLE:
        print(json.dumps({"status": "jev_unavailable"}))
        return

    results = []
    for i, t in enumerate(tests):
        key = "test_%d" % i
        ans = answers.get(key, {})
        results.append({
            "name":       t.get("name", ""),
            "action":     ans.get("choice", "investigate"),
            "confidence": ans.get("confidence", 0),
        })

    print(json.dumps({"status": "ok", "results": results}))


if __name__ == "__main__":
    main()
