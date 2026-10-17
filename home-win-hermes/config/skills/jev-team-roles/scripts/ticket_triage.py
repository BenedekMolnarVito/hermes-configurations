#!/usr/bin/env python3
"""
ticket_triage.py — Triage a ticket: classify owning team + score priority.

Usage:
    python3 ticket_triage.py --input job.json

job.json shape:
    {
        "summary":     "Login button broken on mobile",
        "description": "Users on iOS 17 cannot log in.",
        "teams": {"frontend": "Web/mobile UI", "backend": "API and auth", "qa": "Testing"}
    }

Output (stdout):
    {"status": "ok", "results": {"team": "frontend", "team_confidence": 0.9, "priority_score": 1.8}}
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

from jevlib.jev_client import UNAVAILABLE, choice, score, safe_decide  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Triage a ticket via JEV.")
    parser.add_argument("--input", required=True, help="Path to job JSON file.")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        job = json.load(fh)

    teams = job.get("teams", {"engineering": "General engineering", "product": "Product/design"})

    questions: dict = {
        "team": choice(
            "Which team should own this ticket?",
            teams,
        ),
        "priority": score(
            "How urgently does this ticket need to be addressed?",
            ["low: nice-to-have, no user impact",
             "medium: affects some users, workaround exists",
             "high: blocks users or revenue, immediate attention needed"],
        ),
    }

    state = {
        "summary":     job.get("summary", ""),
        "description": job.get("description", ""),
    }

    answers = safe_decide(state, questions)

    if answers is UNAVAILABLE:
        print(json.dumps({"status": "jev_unavailable"}))
        return

    team_ans     = answers.get("team", {})
    priority_ans = answers.get("priority", {})

    results = {
        "team":             team_ans.get("choice"),
        "team_confidence":  team_ans.get("confidence", 0),
        "priority_score":   priority_ans.get("score", 0),
    }

    print(json.dumps({"status": "ok", "results": results}))


if __name__ == "__main__":
    main()
