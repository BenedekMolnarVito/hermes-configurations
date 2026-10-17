#!/usr/bin/env python
"""
ac_completeness.py — Score acceptance criteria completeness on 5 dimensions.

Usage:
    python ac_completeness.py --input job.json

job.json shape:
    {
        "title": "User can reset password",
        "acceptance_criteria": "Given user on login page, when they click reset, then email is sent."
    }

Output (stdout):
    {"status": "ok", "results": {"completeness_score": 2.1}}
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

# 5-dimension composite score
_DIMENSIONS = {
    "clarity":      "How clearly written and unambiguous are the criteria?",
    "testability":  "How easily can each criterion be verified by a test?",
    "completeness": "How well do the criteria cover the full feature scope?",
    "feasibility":  "How realistic and achievable are the acceptance criteria?",
    "edge_cases":   "How well do the criteria address edge cases and failure modes?",
}

_SCALE = [
    "poor: missing, vague, or untestable",
    "adequate: present but incomplete",
    "good: clear, testable, and sufficiently complete",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Score AC completeness via JEV.")
    parser.add_argument("--input", required=True, help="Path to job JSON file.")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        job = json.load(fh)

    state = {
        "title":               job.get("title", ""),
        "acceptance_criteria": job.get("acceptance_criteria", ""),
    }

    questions = {
        dim: score(question, _SCALE)
        for dim, question in _DIMENSIONS.items()
    }

    answers = safe_decide(state, questions)

    if answers is UNAVAILABLE:
        print(json.dumps({"status": "jev_unavailable"}))
        return

    # Composite: average of 5 dimension scores
    scores = [answers.get(dim, {}).get("score", 0) for dim in _DIMENSIONS]
    composite = sum(scores) / len(scores) if scores else 0

    print(json.dumps({"status": "ok", "results": {"completeness_score": composite}}))


if __name__ == "__main__":
    main()
