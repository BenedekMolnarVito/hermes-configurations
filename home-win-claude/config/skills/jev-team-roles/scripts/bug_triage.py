#!/usr/bin/env python
"""
bug_triage.py — Classify bug severity and check duplicate likelihood.

Usage:
    python bug_triage.py --input job.json

job.json shape:
    {
        "summary":     "App crashes on empty input",
        "description": "Steps: open form, submit empty, app crashes.",
        "severity_options": {
            "critical": "Data loss, crash, or security vulnerability.",
            "major":    "Core feature broken, no workaround.",
            "minor":    "Cosmetic or low-impact issue with workaround."
        }
    }

Output (stdout):
    {"status": "ok", "results": {"severity": "critical", "severity_confidence": 0.95, "duplicate_noul": 0.1}}
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

from jevlib.jev_client import UNAVAILABLE, choice, noul, safe_decide  # noqa: E402

_DEFAULT_SEVERITY = {
    "critical": "Data loss, crash, or security vulnerability.",
    "major":    "Core feature broken, no workaround.",
    "minor":    "Cosmetic or low-impact issue with workaround.",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Triage a bug via JEV.")
    parser.add_argument("--input", required=True, help="Path to job JSON file.")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        job = json.load(fh)

    severity_options = job.get("severity_options", _DEFAULT_SEVERITY)

    state = {
        "summary":     job.get("summary", ""),
        "description": job.get("description", ""),
    }

    questions = {
        "severity":  choice(
            "What is the severity of this bug?",
            severity_options,
        ),
        "duplicate": noul(
            "Is this bug likely a duplicate of an existing open issue?"
        ),
    }

    answers = safe_decide(state, questions)

    if answers is UNAVAILABLE:
        print(json.dumps({"status": "jev_unavailable"}))
        return

    sev_ans = answers.get("severity", {})
    dup_ans = answers.get("duplicate", {})

    results = {
        "severity":             sev_ans.get("choice"),
        "severity_confidence":  sev_ans.get("confidence", 0),
        "duplicate_noul":       dup_ans.get("noul", 0),
    }

    print(json.dumps({"status": "ok", "results": results}))


if __name__ == "__main__":
    main()
