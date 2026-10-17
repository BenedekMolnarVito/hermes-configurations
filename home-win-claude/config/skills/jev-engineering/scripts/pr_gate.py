#!/usr/bin/env python
"""
pr_gate.py — Gate a PR with JEV: risk score, test coverage signal, auth-touch likelihood.

Usage:
    python pr_gate.py --input job.json

job.json shape:
    {
        "title":        "feat: add auth refresh",
        "diff_summary": "Modifies token flow, adds tests for refresh path.",
        "files_changed": ["src/auth.ts", "tests/auth.test.ts"]
    }

Output (stdout):
    {"status": "ok", "results": {"risk_score": 1.2, "has_tests_noul": 0.8, "touches_auth_noul": 0.9}}
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

from jevlib.jev_client import UNAVAILABLE, score, noul, safe_decide  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate a PR via JEV.")
    parser.add_argument("--input", required=True, help="Path to job JSON file.")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        job = json.load(fh)

    questions = {
        "risk": score(
            "How risky is this pull request for production stability?",
            ["low risk: small scope, well-tested",
             "medium risk: moderate changes, partial tests",
             "high risk: broad changes, missing tests or auth-critical"],
        ),
        "has_tests": noul(
            "Does this PR appear to include or update automated tests?"
        ),
        "touches_auth": noul(
            "Does this PR touch authentication, authorization, or security-sensitive code?"
        ),
    }

    answers = safe_decide(job, questions)

    if answers is UNAVAILABLE:
        print(json.dumps({"status": "jev_unavailable"}))
        return

    results = {
        "risk_score":       answers.get("risk", {}).get("score", 0),
        "has_tests_noul":   answers.get("has_tests", {}).get("noul", 0),
        "touches_auth_noul": answers.get("touches_auth", {}).get("noul", 0),
    }

    print(json.dumps({"status": "ok", "results": results}))


if __name__ == "__main__":
    main()
