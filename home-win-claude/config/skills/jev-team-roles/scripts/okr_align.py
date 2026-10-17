#!/usr/bin/env python
"""
okr_align.py — Score a proposal's alignment to each OKR.

Usage:
    python okr_align.py --input job.json

job.json shape:
    {
        "proposal": "Add dark mode to the app",
        "okrs": [
            {"key": "user_retention", "description": "Increase 30-day retention by 10%"},
            {"key": "dev_velocity",   "description": "Ship 2 features per sprint"}
        ]
    }

Output (stdout):
    {"status": "ok", "results": [{"okr_key": "user_retention", "alignment_score": 1.2}, ...]}
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

from jevlib.jev_client import UNAVAILABLE, score, safe_decide  # noqa: E402

_ALIGNMENT_SCALE = [
    "no alignment: proposal does not contribute to this OKR",
    "indirect alignment: proposal loosely supports this OKR",
    "direct alignment: proposal clearly advances this OKR",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Score OKR alignment via JEV.")
    parser.add_argument("--input", required=True, help="Path to job JSON file.")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        job = json.load(fh)

    proposal = job.get("proposal", "")
    okrs = job.get("okrs", [])

    if not okrs:
        print(json.dumps({"status": "ok", "results": []}))
        return

    questions = {
        "okr_%d" % i: score(
            {"question": "How well does this proposal align with the OKR?",
             "proposal": proposal,
             "okr_key":  okr.get("key", ""),
             "okr":      okr.get("description", "")},
            _ALIGNMENT_SCALE,
        )
        for i, okr in enumerate(okrs)
    }

    answers = safe_decide({"note": "okr_align", "proposal": proposal}, questions)

    if answers is UNAVAILABLE:
        print(json.dumps({"status": "jev_unavailable"}))
        return

    results = []
    for i, okr in enumerate(okrs):
        key = "okr_%d" % i
        ans = answers.get(key, {})
        results.append({
            "okr_key":        okr.get("key", ""),
            "alignment_score": ans.get("score", 0),
        })

    print(json.dumps({"status": "ok", "results": results}))


if __name__ == "__main__":
    main()
