#!/usr/bin/env python3
"""
hook_batch_guard.py — pre_tool_call HARD-BLOCK for bulk classify/rank/triage.

Reads one JSON object from stdin:
  {hook_event_name, tool_name, tool_input, session_id, cwd, profile, extra}

Writes AT MOST one JSON directive to stdout:
  {} (noop)
  {"action": "block", "message": "..."}

Behavior:
- Gate: tool_name in {delegate_task, web_extract}.
- LOCAL PREFILTER first (no Jev call):
    Find a top-level list arg of length >= BULK_MIN (=8)
    whose items are dicts or strings
    AND it is NOT a delegate "tasks" list of goal-objects
      (items with a "goal" key → these are normal subtask lists, skip).
    For web_extract: any list arg qualifies regardless.
  If prefilter fails → noop "{}" immediately (Jev not called).
- Only if prefilter matches → call decisions.is_bulk_classify.
  If bulk_p > 0.7 → block.
  Else → noop "{}".

Fail-open: any error → print "{}" and exit 0.

Python 3.9 compatible, stdlib only (plus jevlib).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

BULK_MIN = 8


# ---------------------------------------------------------------------------
# sys.path bootstrap — must happen before any jevlib import
# ---------------------------------------------------------------------------

def _bootstrap_path() -> None:
    """Insert agent-hooks dir into sys.path so `from jevlib import ...` works."""
    hermes_home = os.environ.get("HERMES_HOME", "")
    if hermes_home:
        hooks_dir = pathlib.Path(hermes_home) / "agent-hooks"
    else:
        hooks_dir = pathlib.Path.home() / ".hermes" / "agent-hooks"
    hooks_str = str(hooks_dir)
    if hooks_str not in sys.path:
        sys.path.insert(0, hooks_str)


_bootstrap_path()

from jevlib import decisions  # noqa: E402
from jevlib import envload  # noqa: E402
envload.ensure()
from jevlib.jev_client import UNAVAILABLE  # noqa: E402


# ---------------------------------------------------------------------------
# Prefilter
# ---------------------------------------------------------------------------

def _prefilter_matches(tool_name: str, tool_input: dict) -> bool:
    """
    Return True iff there is a top-level list arg of length >= BULK_MIN
    whose items are dicts or strings, AND it is not a delegate goal-object list.

    For delegate_task: a list where ALL items are dicts with a "goal" key
    is excluded (these are normal subtask lists, not bulk data).
    For web_extract: any qualifying list is included.
    """
    if not isinstance(tool_input, dict):
        return False

    for key, val in tool_input.items():
        if not isinstance(val, list):
            continue
        if len(val) < BULK_MIN:
            continue

        # Items must all be dicts or strings (not ints, etc.)
        if not all(isinstance(item, (dict, str)) for item in val):
            continue

        # For delegate_task: exclude lists where items are goal-objects
        # (dicts that have a "goal" key → these are normal subtask lists)
        if tool_name == "delegate_task":
            if all(isinstance(item, dict) and "goal" in item for item in val):
                continue  # This is a normal tasks list, not bulk data

        return True

    return False


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw)
    except Exception:
        print("{}")
        return

    try:
        _handle(event)
    except Exception:
        print("{}")


def _handle(event: dict) -> None:
    tool_name = event.get("tool_name", "")
    if tool_name not in ("delegate_task", "web_extract"):
        print("{}")
        return

    tool_input = event.get("tool_input") or {}

    # Local prefilter — if it doesn't match, noop immediately (no Jev call)
    if not _prefilter_matches(tool_name, tool_input):
        print("{}")
        return

    # Prefilter matched → ask Jev
    verdict = decisions.is_bulk_classify(tool_name, tool_input)
    if verdict is UNAVAILABLE:
        print("{}")
        return

    bulk_p = verdict.get("bulk_p", 0)
    if bulk_p > 0.7:
        directive = {
            "action": "block",
            "message": (
                "Route this bulk classify/rank/triage through the jev-decisions "
                "skill (scripts/classify_batch.py) instead of an LLM."
            ),
        }
        print(json.dumps(directive))
        return

    print("{}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
