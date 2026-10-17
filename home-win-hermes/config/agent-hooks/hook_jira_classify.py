#!/usr/bin/env python3
"""
hook_jira_classify.py — pre_tool_call MODIFY hook for mcp__sap_jira__jira_create_issue.

Reads one JSON object from stdin:
  {hook_event_name, tool_name, tool_input, session_id, cwd, profile, extra}

Writes AT MOST one JSON directive to stdout:
  {} (noop)
  {"action": "block", "message": "..."}
  {"action": "modify", "args": {...}}

Behavior:
- Gate: tool_name == "mcp__sap_jira__jira_create_issue".
- components from extra.project_components (dict) or {}.
- decisions.jira_classify(issue=tool_input, components).
  • If dup_p > 0.8 → block.
  • Else: build modify args attaching:
    - component: only if caller left it empty AND component_confidence > 0.5
    - priority: only if caller left it empty (future-proofing — not set here unless
      Jev returns a severity field that maps to priority; we skip priority for now
      since the brief only specifies component)
  • If nothing to attach → noop.
  • Else → modify.

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
    if event.get("tool_name") != "mcp__sap_jira__jira_create_issue":
        print("{}")
        return

    tool_input = event.get("tool_input") or {}
    extra = event.get("extra") or {}
    components = extra.get("project_components") or {}

    verdict = decisions.jira_classify(issue=tool_input, components=components)
    if verdict is UNAVAILABLE:
        print("{}")
        return

    dup_p = verdict.get("dup_p", 0)

    # Block if likely duplicate
    if dup_p > 0.8:
        directive = {
            "action": "block",
            "message": "Likely duplicate; verify before creating.",
        }
        print(json.dumps(directive))
        return

    # Build modify args for fields the caller left empty
    modify_args: dict = {}

    # Component: attach only if caller didn't set it and confidence is high enough
    if not tool_input.get("component"):
        comp = verdict.get("component")
        comp_conf = verdict.get("component_confidence", 0)
        if comp and comp_conf > 0.5:
            modify_args["component"] = comp

    if not modify_args:
        print("{}")
        return

    directive = {"action": "modify", "args": modify_args}
    print(json.dumps(directive))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
