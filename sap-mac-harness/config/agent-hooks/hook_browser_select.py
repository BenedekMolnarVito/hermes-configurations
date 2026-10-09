#!/usr/bin/env python3
"""
hook_browser_select.py — pre_tool_call MODIFY+BLOCK hook for browser_click.

Reads one JSON object from stdin:
  {hook_event_name, tool_name, tool_input, session_id, cwd, profile, extra}

Writes AT MOST one JSON directive to stdout:
  {} (noop)
  {"action": "block", "message": "..."}
  {"action": "modify", "args": {"ref": "<ref_id>"}}

Behavior:
- Gate: tool_name == "browser_click".
- candidates from extra.dom_candidates (list). None/empty → noop.
- goal from extra.goal or "".
- decisions.browser_select(goal, candidates):
    • If error_p > 0.7 → block (page in error state).
    • Elif ref and ref != tool_input.ref and pick_confidence > 0.6 → modify.
    • Else → noop "{}".

Fail-open: any error → print "{}" and exit 0.

Python 3.9 compatible, stdlib only (plus jevlib).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys


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
    if event.get("tool_name") != "browser_click":
        print("{}")
        return

    tool_input = event.get("tool_input") or {}
    extra = event.get("extra") or {}

    candidates = extra.get("dom_candidates")
    if not candidates:
        print("{}")
        return

    goal = extra.get("goal", "")

    verdict = decisions.browser_select(goal, candidates)
    if verdict is UNAVAILABLE:
        print("{}")
        return

    error_p = verdict.get("error_p", 0)
    ref = verdict.get("ref")
    pick_confidence = verdict.get("pick_confidence", 0)

    # Priority 1: error state → block
    if error_p > 0.7:
        directive = {
            "action": "block",
            "message": "Page in error/blocking state; re-snapshot before clicking.",
        }
        print(json.dumps(directive))
        return

    # Priority 2: ref mismatch with high confidence → modify
    caller_ref = tool_input.get("ref")
    if ref and ref != caller_ref and pick_confidence > 0.6:
        directive = {
            "action": "modify",
            "args": {"ref": ref},
        }
        print(json.dumps(directive))
        return

    # Default: noop
    print("{}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
