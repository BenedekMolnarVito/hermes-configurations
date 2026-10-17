#!/usr/bin/env python
"""
agent_state_hooks.py — Claude Code hooks for the rate-limit-proof persistence protocol.

Usage (from settings.json):
  python agent_state_hooks.py session-start      # SessionStart: inject .agent/ state
  python agent_state_hooks.py rate-limit         # StopFailure(rate_limit): leave a trace
  python agent_state_hooks.py subagent-contract  # PreToolUse(Agent): JEV bulk guard + model route,
                                                 #   caveman rule, return contract
  python agent_state_hooks.py skill-route        # UserPromptSubmit: JEV-picked skill hint

State dir: $AGENT_STATE_DIR if it exists, else the nearest `.agent/` walking up from the
hook's cwd (stops at the git root). No state dir → session-start/return contract are no-ops;
the caveman I/O rule is appended to every Agent prompt regardless.

JEV (TypeSafe, jevlib/ next to this file, config jev-guard.json): needs TYPESAFE_API_KEY.
`[jev-skip]` in an Agent prompt skips JEV for that dispatch.

Fail-open: any error (incl. JEV outage) → no output / no JEV change, exit 0. Stdlib only.
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import sys

HOOK_DIR = pathlib.Path(__file__).resolve().parent
JEV_SKIP = "[jev-skip]"
BULK_MIN = 8
BULK_WORDS = re.compile(r"\b(?:classif|re-?rank|rank|triage|categori[sz]|prioriti[sz]|label)", re.I)
LIST_LINE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+\S", re.M)
AGENT_MODELS = {"haiku", "sonnet", "opus"}
AGENT_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
PROGRESS_LINES = 80
INTERRUPTION_LINES = 5
CONTRACT_MARKER = "[return-contract]"
CAVEMAN_MARKER = "[caveman-io]"
CAVEMAN_RULE = (f"{CAVEMAN_MARKER} Caveman I/O: report + reply terse — no articles/filler/pleasantries, "
                 "fragments OK, `→` for causality. Code, paths, symbols, commands, errors, numbers exact.")
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
    parts = [f"Persistence: resume state at {s}. Trust files over recall; "
             "check git state per repo, continue first unfinished task."]
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
            f.write(f"- {ts} RATE LIMIT (session {sid}). Resume from PROGRESS.md Now/Next\n")


def subagent_contract(event: dict) -> None:
    if event.get("tool_name") != "Agent":
        return
    tool_input = dict(event.get("tool_input") or {})
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str):
        return
    if JEV_SKIP not in prompt:
        try:
            deny = _jev_agent(tool_input, prompt)
        except Exception:
            deny = None
        if deny:
            _emit({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                          "permissionDecision": "deny",
                                          "permissionDecisionReason": deny}})
            return
    add = []
    if CAVEMAN_MARKER not in prompt:
        add.append(CAVEMAN_RULE)
    s = _state_dir(event.get("cwd", ""))
    if s and CONTRACT_MARKER not in prompt and ".agent/reports" not in prompt:
        add.append(f"{CONTRACT_MARKER} Full result → {(s / 'reports').as_posix()}/<task-id>.md "
                   "(task id from brief, else short slug) BEFORE returning. "
                   "Reply ≤10 lines: status, files changed, blockers, report path.")
    if not add and tool_input == (event.get("tool_input") or {}):
        return
    if add:
        tool_input["prompt"] = prompt + "\n\n" + "\n".join(add)
    _emit({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "permissionDecision": "allow",
                                  "permissionDecisionReason": "JEV route / caveman I/O rule / return contract",
                                  "updatedInput": tool_input}})


def _jevlib():
    if str(HOOK_DIR) not in sys.path:
        sys.path.insert(0, str(HOOK_DIR))
    from jevlib import config, decisions, envload, jev_client
    envload.ensure()
    return config, decisions, jev_client


def _jev_agent(tool_input: dict, prompt: str) -> str | None:
    """Bulk-classify guard (returns deny reason) + model/effort route (mutates tool_input)."""
    config, decisions, jc = _jevlib()
    cfg = config.load_config()
    agent = tool_input.get("subagent_type") or "general-purpose"
    if agent in cfg["routing"].get("pinned_agents", []):
        return None
    if len(LIST_LINE.findall(prompt)) >= BULK_MIN and BULK_WORDS.search(prompt):
        ans = jc.safe_decide({"brief": prompt[:4000]}, {"bulk": jc.noul(
            "Is this brief handing an LLM a bulk classify/rank/triage job over a list of items "
            "that a typed classifier should do instead?")})
        if ans is not jc.UNAVAILABLE and (ans.get("bulk", {}).get("noul") or 0) > 0.7:
            jc.log_event("bulk_block", agent=tool_input.get("subagent_type"))
            return ("JEV: bulk classify/rank/triage job → use jev-decisions skill (classify_batch.py / "
                    f"rerank.py), not a subagent. False positive → add {JEV_SKIP} to the prompt.")
    if tool_input.get("model"):
        return None
    goal = f"{tool_input.get('description', '')}\n{prompt[:3000]}"
    verdict = decisions.complexity_tier([goal])
    if verdict is jc.UNAVAILABLE or not verdict.get("confident"):
        return None
    tier = verdict["tiers"][0]
    route = config.route_for_tier(tier, cfg)
    if route.get("model") not in AGENT_MODELS:  # e.g. a Hermes jev-guard.json via HERMES_HOME
        return None
    tool_input["model"] = route["model"]
    if not tool_input.get("effort") and route.get("effort") in AGENT_EFFORTS:
        tool_input["effort"] = route["effort"]
    jc.log_event("route", agent=agent, tier=tier, model=route["model"])
    return None


def _skill_roster() -> list:
    home = HOOK_DIR.parent
    dirs = [("", home / "skills")]
    try:
        reg = json.loads(_read(home / "plugins" / "installed_plugins.json") or "{}")
        for key, installs in (reg.get("plugins") or {}).items():
            for inst in installs[:1]:
                dirs.append((key.split("@")[0] + ":", pathlib.Path(inst["installPath"]) / "skills"))
    except Exception:
        pass
    roster = {}
    for prefix, d in dirs:
        for md in sorted(d.glob("*/SKILL.md")) if d.is_dir() else []:
            head = _read(md)[:1500]
            name = re.search(r"^name:\s*(.+)$", head, re.M)
            desc = re.search(r"^description:\s*(.+)$", head, re.M)
            if name:
                roster[prefix + name.group(1).strip().strip("\"'")] = \
                    (desc.group(1).strip().strip("\"'") if desc else "")[:300]
    return roster


def skill_route(event: dict) -> None:
    text = (event.get("prompt") or "").strip()
    if len(text) < 20 or text.startswith("/"):
        return
    roster = _skill_roster()
    if not roster:
        return
    _, _, jc = _jevlib()
    ans = jc.safe_decide({"request": text[:4000]}, {
        "need": jc.noul("Does this request need a specialized skill/procedure at all?"),
        "which": jc.choice("Which skill best fits this request?", roster)})
    if ans is jc.UNAVAILABLE:
        return
    which = ans.get("which", {})
    if (ans.get("need", {}).get("noul") or 0) < 0.5 or (which.get("confidence") or 0) < 0.6 \
            or which.get("choice") not in roster:
        return
    jc.log_event("skill_route", skill=which["choice"], confidence=which["confidence"])
    _emit({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext":
           f"JEV skill route: `{which['choice']}` (conf {which['confidence']:.2f}). "
           "Load via Skill tool if it fits; ignore otherwise."}})


COMMANDS = {"session-start": session_start, "rate-limit": rate_limit,
            "subagent-contract": subagent_contract, "skill-route": skill_route}


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
