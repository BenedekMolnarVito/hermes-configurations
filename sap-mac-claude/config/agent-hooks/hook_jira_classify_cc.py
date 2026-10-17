#!/usr/bin/env python3
"""
hook_jira_classify_cc.py — PreToolUse guard/enricher for Jira issue creation.

Claude Code adapter of hook_jira_classify.py.
Fires on mcp__jira__create_issue (mcp-atlassian tool name).

Two behaviors:
1. If JEV says likely duplicate (dup_p > 0.8) → deny with reason.
2. If caller left component blank and JEV is confident (> 0.5) → inject component
   via updatedInput.

Output format uses Claude Code's hookSpecificOutput.permissionDecision /
updatedInput instead of Hermes action/modify protocol.

Fail-open: any error → print "{}" exit 0.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

# mcp-atlassian tool name for Jira issue creation.
# Standard naming: mcp__jira__create_issue
# If your server registers a different name, update this constant.
JIRA_CREATE_TOOL = "mcp__jira__create_issue"


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
    if payload.get("tool_name") != JIRA_CREATE_TOOL:
        print("{}")
        return

    tool_input = payload.get("tool_input") or {}

    # project_components not available in Claude Code context — pass empty dict.
    # Future: could be injected via a SessionStart hook that reads project config.
    verdict = decisions.jira_classify(issue=tool_input, components={})
    if verdict is UNAVAILABLE:
        print("{}")
        return

    # Block likely duplicates
    if verdict.get("dup_p", 0) > 0.8:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Likely duplicate issue — verify before creating.",
            }
        }))
        return

    # Inject component if caller left it blank and JEV is confident
    comp = verdict.get("component")
    comp_conf = verdict.get("component_confidence", 0)
    if comp and comp_conf > 0.5 and not tool_input.get("component"):
        updated = dict(tool_input)
        updated["component"] = comp
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "updatedInput": updated,
            }
        }))
        return

    print("{}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
