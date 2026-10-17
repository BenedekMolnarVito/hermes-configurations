#!/usr/bin/env python3
"""
hook_skill_route.py — pre_llm_call ADVISE hook.

Reads one JSON object from stdin.
Builds a skill roster from home()/skills/*/SKILL.md frontmatter.
Calls decisions.skill_route to find the best match.
If confidence >= 0.30, prints a JSON object injecting context.
Any error → fail-open: print "{}" exit 0.

stdlib only. Python 3.9 compatible.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys


def _setup_path():
    """Insert agent-hooks dir onto sys.path using HERMES_HOME or ~/.hermes."""
    hermes_home_raw = os.environ.get("HERMES_HOME", "")
    if hermes_home_raw:
        hooks_dir = pathlib.Path(hermes_home_raw) / "agent-hooks"
    else:
        hooks_dir = pathlib.Path.home() / ".hermes" / "agent-hooks"
    hooks_str = str(hooks_dir)
    if hooks_str not in sys.path:
        sys.path.insert(0, hooks_str)


def _build_roster(skills_dir: pathlib.Path) -> list:
    """
    Walk skills_dir/*/SKILL.md, read first 1200 chars, extract name + description.
    Returns list of (name, desc) for every SKILL.md that has a name.
    """
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


def main():
    _setup_path()

    # Import after path setup
    from jevlib import config, decisions, envload
    envload.ensure()
    from jevlib.jev_client import UNAVAILABLE

    raw = sys.stdin.read()
    payload = json.loads(raw)

    # Only handle pre_llm_call
    if payload.get("hook_event_name") != "pre_llm_call":
        return

    # Extract user message
    user_msg = (payload.get("extra") or {}).get("user_message") or ""
    if not user_msg.strip():
        return

    # Build skill roster
    skills_dir = config.home() / "skills"
    roster = _build_roster(skills_dir)
    if not roster:
        return

    # Ask JEV
    verdict = decisions.skill_route(user_msg, roster)
    if verdict is UNAVAILABLE:
        return
    if not verdict.get("skill"):
        return
    if verdict.get("confidence", 0) < 0.30:
        return

    skill_name = verdict["skill"]
    print(json.dumps({
        "context": (
            f'Relevant skill: {skill_name}. '
            f'Load it with skill_view("{skill_name}") before acting.'
        )
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
