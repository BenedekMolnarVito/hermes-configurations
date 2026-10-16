"""
jevlib/decisions.py — High-level decision helpers via JEV.

All functions return a plain dict OR the UNAVAILABLE sentinel (fail-open).

stdlib only. Python 3.9 compatible.

Public API
----------
complexity_tier(goals)       Batch-classify task complexity; returns tiers dict.
skill_route(user_text, roster) Route a request to the best matching skill.
citation_claims(claims)      Verdict each claim against its source.
"""
from __future__ import annotations

from . import config
from .jev_client import UNAVAILABLE, noul, choice, score, safe_decide

# ---------------------------------------------------------------------------
# Complexity level descriptions (used as score criteria)
# ---------------------------------------------------------------------------

# Three mutually-exclusive complexity bands, each with explicit criteria + concrete
# examples (per Agentic-Design-KB lesson 5-2: disambiguate fuzzy decision boundaries
# with explicit criteria and examples, NOT a vaguer self-reported score). JEV scores a
# task as a float index into this ordinal list: ~0.0 = band 0 (quick), ~1.0 = band 1
# (standard), ~2.0 = band 2 (deep). Thresholds in jev-guard.json sit at the band
# midpoints (standard_min=0.5 = the 0<->1 boundary, deep_min=1.5 = the 1<->2 boundary),
# so a task scored firmly in band 0 routes to the cheapest competent model (haiku).
_COMPLEXITY_LEVELS = [
    # Band 0 — QUICK (haiku): mechanical, no design, no cross-file reasoning.
    "QUICK — purely mechanical, no design judgement and no cross-file reasoning. "
    "The exact change is already specified: edit one file to a value/content that is "
    "given, apply a verbatim snippet, add a key to a JSON/YAML list, rename a symbol, "
    "bump a dependency, or run a verification command that is provided. Examples: set "
    "a named config key to a given value; append given strings to an array; write a "
    "file whose full source is supplied verbatim and run its given test; fix a typo.",
    # Band 1 — STANDARD (sonnet): scoped build with explicit contract.
    "STANDARD — a well-scoped change across one or two files where you write the logic "
    "yourself but the interface/contract and acceptance criteria are explicit and the "
    "approach is already decided. Bounded judgement, no architecture or investigation. "
    "Examples: implement a hook that follows a documented stdin/stdout protocol; write "
    "a function from a precise signature plus input/output examples; a localized "
    "bugfix with a known cause.",
    # Band 2 — DEEP (opus): design, ambiguity, root-cause, cross-cutting.
    "DEEP — the correct approach is NOT yet decided and the task needs reasoning across "
    "components: interface or system design, root-cause debugging, a multi-file "
    "refactor, investigating unknown or surprising runtime behavior, or resolving "
    "genuine ambiguity. Examples: determine why a runtime monkey-patch never applies "
    "given a plugin-host architecture; design a multi-agent orchestration; trace a bug "
    "of unknown origin across modules.",
]

# Tier ordering for max-tier tracking
_TIER_ORDER = {"quick": 0, "standard": 1, "deep": 2}


def complexity_tier(goals: list) -> dict:
    """
    Classify each goal's complexity tier in a SINGLE batched JEV request.

    Parameters
    ----------
    goals : list of str

    Returns
    -------
    {"tiers": {i: tier}, "max_tier": str, "confident": bool}
    UNAVAILABLE if JEV is unavailable.
    Empty goals → {"tiers": {}, "max_tier": "standard", "confident": False}.
    """
    if not goals:
        return {"tiers": {}, "max_tier": "standard", "confident": False}

    questions = {
        "task_%d" % i: score(
            {"question": "How complex is this task for an AI coding agent?", "task": g},
            _COMPLEXITY_LEVELS,
        )
        for i, g in enumerate(goals)
    }

    answers = safe_decide({"note": "independent task complexity"}, questions)
    if answers is UNAVAILABLE:
        return UNAVAILABLE

    cfg = config.load_config()
    tiers: dict = {}
    confident = True
    max_tier = "quick"

    for i in range(len(goals)):
        key = "task_%d" % i
        ans = answers.get(key, {})
        s = ans.get("score", 1.0)
        c = ans.get("confidence", 1.0)
        if c < 0.5:
            confident = False
        tier = config.tier_for_score(s, cfg)
        tiers[i] = tier
        if _TIER_ORDER.get(tier, 0) > _TIER_ORDER.get(max_tier, 0):
            max_tier = tier

    return {"tiers": tiers, "max_tier": max_tier, "confident": confident}


def skill_route(user_text: str, roster: list) -> dict:
    """
    Route a user request to the best matching skill.

    Parameters
    ----------
    user_text : str
    roster    : list of (name, desc) tuples

    Returns
    -------
    {"skill": str|None, "confidence": float}  or  UNAVAILABLE.
    Empty roster → UNAVAILABLE.
    """
    if not roster:
        return UNAVAILABLE

    questions = {
        "need": noul("Does this request need a specialized skill/procedure at all?"),
        "which": choice(
            "Which skill best fits this request?",
            {name: desc for name, desc in roster},
        ),
    }

    answers = safe_decide({"request": user_text}, questions)
    if answers is UNAVAILABLE:
        return UNAVAILABLE

    need_val = answers.get("need", {}).get("noul", 0)
    if need_val < 0.30:
        return {"skill": None, "confidence": need_val}

    which_ans = answers.get("which", {})
    return {
        "skill": which_ans.get("choice"),
        "confidence": which_ans.get("confidence", 0),
    }


def citation_claims(claims: list) -> dict:
    """
    Evaluate each claim against its source.

    Parameters
    ----------
    claims : list of {"claim": str, "source": str}

    Returns
    -------
    {i: {"verdict": str, "confidence": float}}  or  UNAVAILABLE.
    Empty claims → UNAVAILABLE.
    """
    if not claims:
        return UNAVAILABLE

    verdict_options = {
        "supports": "The source directly evidences the claim.",
        "contradicts": "The source states the opposite.",
        "says_nothing": "The source is silent on this claim.",
    }

    questions = {
        "claim_%d" % i: choice(
            {
                "question": "Does the source support the claim?",
                "claim": c["claim"],
                "source": c["source"],
            },
            verdict_options,
        )
        for i, c in enumerate(claims)
    }

    answers = safe_decide({"note": "citation grounding"}, questions)
    if answers is UNAVAILABLE:
        return UNAVAILABLE

    result: dict = {}
    for i in range(len(claims)):
        key = "claim_%d" % i
        ans = answers.get(key, {})
        result[i] = {
            "verdict": ans.get("choice") or "says_nothing",
            "confidence": ans.get("confidence", 0),
        }

    return result


def browser_select(goal: str, candidates: list) -> dict:
    """
    Select the best element from a list of DOM candidates.

    Parameters
    ----------
    goal       : str  — the user intent / goal for the click
    candidates : list of {ref_id: str, label: str}

    Returns
    -------
    {"ref": str|None, "pick_confidence": float, "error_p": float}
    UNAVAILABLE if candidates is empty or JEV is unavailable.
    """
    if not candidates:
        return UNAVAILABLE

    criteria = {c["ref_id"]: c.get("label", "") for c in candidates}
    criteria["none"] = "No suitable element"

    questions = {
        "pick": choice(
            {"question": "Which element best achieves the goal?", "goal": goal},
            criteria,
        ),
        "error": noul(
            "Is the page in an error/captcha/auth-wall state blocking the goal?"
        ),
    }

    state = {"candidates": candidates}
    answers = safe_decide(state, questions)
    if answers is UNAVAILABLE:
        return UNAVAILABLE

    pick_ans = answers.get("pick", {})
    error_ans = answers.get("error", {})

    picked = pick_ans.get("choice")
    ref = None if picked == "none" else picked

    return {
        "ref": ref,
        "pick_confidence": pick_ans.get("confidence") or 0,
        "error_p": error_ans.get("noul") or 0,
    }


def jira_classify(issue: dict, components: dict) -> dict:
    """
    Classify a Jira issue's severity, duplicate likelihood, and owning component.

    Parameters
    ----------
    issue      : dict — the issue fields (summary, description, etc.)
    components : dict — {name: description} map of project components

    Returns
    -------
    {"severity": float, "dup_p": float,
     "component": str|None, "component_confidence": float}  (component keys
     omitted when components is empty)
    UNAVAILABLE if JEV is unavailable.
    """
    questions: dict = {
        "severity": score(
            "How severe is this issue?",
            ["trivial", "minor", "major", "critical"],
        ),
        "dup": noul(
            "Is this a duplicate of an existing open issue in state?"
        ),
    }

    if components:
        questions["component"] = choice(
            "Which component owns this issue?",
            components,
        )

    answers = safe_decide(issue, questions)
    if answers is UNAVAILABLE:
        return UNAVAILABLE

    sev_ans = answers.get("severity", {})
    dup_ans = answers.get("dup", {})

    result: dict = {
        "severity": sev_ans.get("score") or 0,
        "dup_p": dup_ans.get("noul") or 0,
    }

    if components:
        comp_ans = answers.get("component", {})
        result["component"] = comp_ans.get("choice") or None
        result["component_confidence"] = comp_ans.get("confidence") or 0

    return result


def is_bulk_classify(tool_name: str, tool_input) -> dict:
    """
    Check whether the agent is about to hand a bulk classify/rank/triage job
    to an LLM that should go through a typed classifier instead.

    Parameters
    ----------
    tool_name  : str
    tool_input : dict|any — the tool's argument dict

    Returns
    -------
    {"bulk_p": float}  or  UNAVAILABLE.
    """
    arg_keys = sorted(list(tool_input.keys())) if isinstance(tool_input, dict) else []
    description = "tool=%s keys=%s" % (tool_name, arg_keys)

    questions = {
        "bulk": noul(
            "Is the agent about to hand an LLM a bulk classify/rank/triage job"
            " over a list of items that a typed classifier should do instead?"
        ),
    }

    state = {"tool": tool_name, "arg_keys": arg_keys}
    answers = safe_decide(state, questions)
    if answers is UNAVAILABLE:
        return UNAVAILABLE

    bulk_ans = answers.get("bulk", {})
    return {"bulk_p": bulk_ans.get("noul") or 0}


def is_bulk_io(tool_name: str, io_shape: dict) -> dict:
    """
    Judge whether a bulky read/write/extract about to run DIRECTLY in the
    orchestrator should instead be CHUNKED across subagents and reassembled by
    a synthesis agent (per Agentic-Design-KB Domain 1 parallel/hub-and-spoke +
    Domain 5.3/5.4: delegate large scans to a subagent that returns a distilled
    finding; keep bulk tokens out of the long-running orchestrator context).

    The caller does the cheap MECHANICAL prefilter (sizes/counts) locally and
    only calls this when the shape is already bulky — this helper adds the
    JUDGEMENT the prefilter cannot make: a bulky read the agent genuinely needs
    verbatim in its own context to reason over (e.g. the one file it is editing)
    must NOT be chunked, whereas a bulk scan/extract/generate whose only purpose
    is to be distilled or produced in pieces SHOULD be.

    Parameters
    ----------
    tool_name : str   — read_file | web_extract | write_file (the bulky-IO tools)
    io_shape  : dict  — compact, NON-content descriptor of the call, e.g.
        {"op": "read", "lines": 1900, "path_hint": "logs/app.log"}
        {"op": "extract", "url_count": 9, "char_limit": 40000}
        {"op": "write", "content_chars": 42000, "path_hint": "report.md"}
        (NEVER the raw content — only sizes/counts/hints, to keep the Jev
         request small and secret-free.)

    Returns
    -------
    {"chunk_p": float, "confidence": float}  or  UNAVAILABLE.
    chunk_p is the probability the call should be chunked+synthesized rather
    than run directly.
    """
    op = io_shape.get("op", "io")
    questions = {
        "chunk": noul(
            "Would running this bulky %s DIRECTLY in the orchestrator flood its "
            "context, such that it should instead be split into chunks handed to "
            "subagents and reassembled by a synthesis agent? Answer HIGH only when "
            "the bulk volume exists to be distilled, scanned, extracted, or "
            "produced piecewise; answer LOW when the agent genuinely needs this "
            "content verbatim in its own context to reason over or edit it, or "
            "when the volume is modest." % op
        ),
    }

    answers = safe_decide(io_shape, questions)
    if answers is UNAVAILABLE:
        return UNAVAILABLE

    chunk_ans = answers.get("chunk", {})
    return {
        "chunk_p": chunk_ans.get("noul") or 0,
        "confidence": chunk_ans.get("confidence") or 0,
    }

