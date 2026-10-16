#!/usr/bin/env python3
"""
hook_skill_route_cc.py — Claude Code UserPromptSubmit adapter for hook_skill_route.py.

Claude Code sends: {"session_id": ..., "transcript": [...], "hook_event_name": "UserPromptSubmit"}
The underlying hook_skill_route.py expects hook_event_name=="pre_llm_call" and extra.user_message.

This wrapper adapts the payload, then runs the same routing logic inline.
Fail-open: any error prints "{}" and exits 0.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys


def _setup_path():
    hermes_home_raw = os.environ.get("HERMES_HOME", "")
    if hermes_home_raw:
        hooks_dir = pathlib.Path(hermes_home_raw) / "agent-hooks"
    else:
        hooks_dir = pathlib.Path.home() / ".hermes" / "agent-hooks"
    hooks_str = str(hooks_dir)
    if hooks_str not in sys.path:
        sys.path.insert(0, hooks_str)


def _build_roster(skills_dir: pathlib.Path) -> list:
    roster = []
    if not skills_dir.is_dir():
        return roster
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            text = skill_md.read_text(encoding="utf-8", errors="replace")[:1200]
        except Exception:
            continue
        name_m = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
        desc_m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        if not name_m:
            continue
        name = name_m.group(1).strip().strip("\"'")
        desc = desc_m.group(1).strip().strip("\"'") if desc_m else ""
        roster.append((name, desc))
    return roster


def _extract_user_message(payload: dict) -> str:
    """Extract the user's latest message from a Claude Code UserPromptSubmit payload."""
    # Direct prompt field (Claude Code sends this)
    prompt = payload.get("prompt", "")
    if prompt:
        return str(prompt)
    # Fallback: last user turn in transcript
    transcript = payload.get("transcript") or []
    for turn in reversed(transcript):
        if isinstance(turn, dict) and turn.get("role") == "user":
            content = turn.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        return part.get("text", "")
    return ""


def main():
    _setup_path()

    from jevlib import config, decisions, envload
    envload.ensure()
    from jevlib.jev_client import UNAVAILABLE

    raw = sys.stdin.read()
    payload = json.loads(raw)

    user_msg = _extract_user_message(payload)
    if not user_msg.strip():
        return

    skills_dir = config.home() / "skills"
    roster = _build_roster(skills_dir)
    if not roster:
        return

    verdict = decisions.skill_route(user_msg, roster)
    if verdict is UNAVAILABLE:
        return
    if not verdict.get("skill"):
        return
    if verdict.get("confidence", 0) < 0.30:
        return

    skill_name = verdict["skill"]
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                f'Relevant skill: {skill_name}. '
                f'Load it with the Skill tool for "{skill_name}" before acting.'
            )
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
