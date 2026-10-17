#!/usr/bin/env python3
"""
hook_batch_guard_cc.py — PreToolUse guard for bulk classify/rank/triage via Agent.

Claude Code adapter of hook_batch_guard.py.
Fires on the Agent tool (equivalent of Hermes delegate_task).

Blocks when the tool input contains a top-level list of >=8 dicts/strings
that are NOT subtask goal-objects — i.e., bulk data being routed to an LLM
instead of JEV's batch API.

Fail-open: any error → print "{}" exit 0.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

BULK_MIN = 8


def _bootstrap_path() -> None:
    hermes_home = os.environ.get("HERMES_HOME", "")
    hooks_dir = (pathlib.Path(hermes_home) if hermes_home else pathlib.Path.home() / ".hermes") / "agent-hooks"
    s = str(hooks_dir)
    if s not in sys.path:
        sys.path.insert(0, s)


_bootstrap_path()

from jevlib import decisions, envload  # noqa: E402
from jevlib.jev_client import UNAVAILABLE  # noqa: E402
envload.ensure()


def _prefilter_matches(tool_input: dict) -> bool:
    if not isinstance(tool_input, dict):
        return False
    for val in tool_input.values():
        if not isinstance(val, list) or len(val) < BULK_MIN:
            continue
        if not all(isinstance(item, (dict, str)) for item in val):
            continue
        # Normal Agent subtask lists have items with a "prompt" or "description" key;
        # skip those — they're legitimate multi-task dispatches, not bulk data.
        if all(isinstance(item, dict) and ("prompt" in item or "description" in item or "goal" in item) for item in val):
            continue
        return True
    return False


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        print("{}")
        return

    try:
        _handle(payload)
    except Exception:
        print("{}")


def _handle(payload: dict) -> None:
    # Only fire on Agent tool
    if payload.get("tool_name") != "Agent":
        print("{}")
        return

    tool_input = payload.get("tool_input") or {}

    if not _prefilter_matches(tool_input):
        print("{}")
        return

    verdict = decisions.is_bulk_classify("delegate_task", tool_input)
    if verdict is UNAVAILABLE:
        print("{}")
        return

    if verdict.get("bulk_p", 0) > 0.7:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "Route this bulk classify/rank/triage through the jev-decisions "
                    "skill (scripts/classify_batch.py) instead of an LLM agent."
                ),
            }
        }))
        return

    print("{}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
