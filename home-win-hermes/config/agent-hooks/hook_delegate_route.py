#!/usr/bin/env python3
"""
hook_delegate_route.py — pre_tool_call hook for delegate_task routing via Jev.

Reads one JSON object from stdin:
  {hook_event_name, tool_name, tool_input, session_id, cwd, profile, extra}

Writes AT MOST one JSON directive to stdout:
  {} (noop) OR {"action": "modify", "args": {"tasks": [...]}}

Fail-open: any error → print "{}" and exit 0.

Behavior:
- If tool_name != "delegate_task" → noop.
- If tasks empty → noop.
- Calls decisions.complexity_tier(goals); UNAVAILABLE → noop.
- For each task: injects model+provider from route (unless task already has model set).
- If JEVGUARD_EFFORT_PER_CALL=="1" → also injects reasoning_effort per task.
- If caveman.enabled("subagent_brief") → compress context+goal when present.
- ACHIEVABLE effort: if JEVGUARD_EFFORT_PER_CALL!="1" AND JEVGUARD_SKIP_CONFIG_WRITE!="1":
    runs `hermes config set delegation.reasoning_effort <eff>` for batch max tier
    (best-effort, wrapped in try/except).
- If nothing changed → noop.

Python 3.9 compatible, stdlib only (plus jevlib).
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
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

from jevlib import config, decisions, caveman  # noqa: E402  (after path fix)
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
    # Only act on delegate_task pre_tool_call
    if event.get("tool_name") != "delegate_task":
        print("{}")
        return

    tool_input = event.get("tool_input") or {}
    tasks = tool_input.get("tasks") or []
    if not tasks:
        print("{}")
        return

    goals = [t.get("goal", "") for t in tasks]

    # Ask Jev for complexity tiers
    verdict = decisions.complexity_tier(goals)
    if verdict is UNAVAILABLE:
        print("{}")
        return

    cfg = config.load_config()
    tiers = verdict.get("tiers", {})
    max_tier = verdict.get("max_tier", "standard")

    per_call_effort = os.environ.get("JEVGUARD_EFFORT_PER_CALL", "") == "1"
    caveman_on = caveman.enabled("subagent_brief")

    new_tasks = []
    changed = False

    for i, task in enumerate(tasks):
        nt = dict(task)  # shallow copy
        tier = tiers.get(i, "standard")
        route = config.route_for_tier(tier, cfg)

        # Inject model+provider only if task has no explicit model
        if not nt.get("model"):
            nt["model"] = route["model"]
            nt["provider"] = route["provider"]
            changed = True

        # Per-call effort (IDEAL branch, off by default)
        if per_call_effort:
            nt["reasoning_effort"] = route["reasoning_effort"]
            changed = True

        # Caveman compression of context and goal
        if caveman_on:
            for field in ("context", "goal"):
                if field in nt:
                    original = nt[field]
                    compressed = caveman.compress(original)
                    if compressed != original:
                        nt[field] = compressed
                        changed = True

        new_tasks.append(nt)

    # ACHIEVABLE effort: set config-wide reasoning_effort for batch max tier
    if not per_call_effort and os.environ.get("JEVGUARD_SKIP_CONFIG_WRITE", "") != "1":
        try:
            max_route = config.route_for_tier(max_tier, cfg)
            eff = max_route["reasoning_effort"]
            subprocess.run(
                ["hermes", "config", "set", "delegation.reasoning_effort", eff],
                capture_output=True,
                timeout=10,
            )
        except Exception:
            pass  # best-effort, never fail the hook

    if not changed:
        print("{}")
        return

    directive = {"action": "modify", "args": {"tasks": new_tasks}}
    print(json.dumps(directive))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
