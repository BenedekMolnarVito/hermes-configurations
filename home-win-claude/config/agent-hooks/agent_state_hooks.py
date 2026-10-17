#!/usr/bin/env python
"""
agent_state_hooks.py — Claude Code hooks for the rate-limit-proof persistence protocol.

Usage (from settings.json):
  python agent_state_hooks.py session-start      # SessionStart: inject .agent/ state
  python agent_state_hooks.py rate-limit         # StopFailure(rate_limit): leave a trace
  python agent_state_hooks.py subagent-contract  # PreToolUse(Agent): append return contract

State dir: $AGENT_STATE_DIR if it exists, else the nearest `.agent/` walking up from the
hook's cwd (stops at the git root). No state dir → every subcommand is a no-op, so this is
free in repos that don't use the protocol.

Fail-open: any error → no output, exit 0. Stdlib only.
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import sys

PROGRESS_LINES = 80
INTERRUPTION_LINES = 5
CONTRACT_MARKER = "[return-contract]"
GLOBAL_LOG = pathlib.Path(__file__).with_name("interruptions.log")


def _state_dir(cwd: str) -> pathlib.Path | None:
    env = os.environ.get("AGENT_STATE_DIR", "")
    if env and pathlib.Path(env).expanduser().is_dir():
        return pathlib.Path(env).expanduser()
    d = pathlib.Path(cwd or os.getcwd()).resolve()
    for p in (d, *d.parents):
        if (p / ".agent").is_dir():
            return p / ".agent"
        if (p / ".git").exists():
            break
    return None


def _read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj))


def session_start(event: dict) -> None:
    s = _state_dir(event.get("cwd", ""))
    if not s:
        return
    parts = [f"Persistence protocol: resume state found at {s}. Trust these files over recollection; "
             "verify git state in every repo, then continue with the first unfinished task."]
    progress = _read(s / "PROGRESS.md").splitlines()[:PROGRESS_LINES]
    if progress:
        parts.append("--- PROGRESS.md ---\n" + "\n".join(progress))
    rows = [ln for ln in _read(s / "TASKS.md").splitlines()
            if ln.startswith("|") and "---" not in ln and "| done" not in ln and "| ID " not in ln]
    if rows:
        parts.append("--- TASKS.md (not done) ---\n" + "\n".join(rows))
    hits = [ln for ln in _read(s / "INTERRUPTIONS.md").splitlines() if ln.strip()][-INTERRUPTION_LINES:]
    if hits:
        parts.append("--- INTERRUPTIONS.md (latest) ---\n" + "\n".join(hits))
    _emit({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                  "additionalContext": "\n\n".join(parts)}})


def rate_limit(event: dict) -> None:
    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    sid = event.get("session_id", "?")
    cwd = event.get("cwd", "")
    with GLOBAL_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{ts}\t{sid}\t{cwd}\n")
    s = _state_dir(cwd)
    if s:
        with (s / "INTERRUPTIONS.md").open("a", encoding="utf-8") as f:
            f.write(f"- {ts} RATE LIMIT HIT (session {sid}). Resume from Now/Next in PROGRESS.md\n")


def subagent_contract(event: dict) -> None:
    if event.get("tool_name") != "Agent":
        return
    tool_input = dict(event.get("tool_input") or {})
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str) or CONTRACT_MARKER in prompt or ".agent/reports" in prompt:
        return
    s = _state_dir(event.get("cwd", ""))
    if not s:
        return
    reports = (s / "reports").as_posix()
    tool_input["prompt"] = (
        f"{prompt}\n\n{CONTRACT_MARKER} Write your full result to {reports}/<task-id>.md "
        "(task id from the brief, else a short slug) BEFORE returning. "
        "Your reply: at most 10 lines — status, files changed, blockers, report path."
    )
    _emit({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "permissionDecision": "allow",
                                  "permissionDecisionReason": "agent-state return contract appended",
                                  "updatedInput": tool_input}})


COMMANDS = {"session-start": session_start, "rate-limit": rate_limit,
            "subagent-contract": subagent_contract}


def main() -> None:
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        cmd = COMMANDS[sys.argv[1]]
        raw = sys.stdin.read()
        cmd(json.loads(raw) if raw.strip() else {})
    except Exception:
        pass


if __name__ == "__main__":
    main()
