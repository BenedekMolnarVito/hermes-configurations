"""
jevlib/config.py — Config loader for Jev-Guard.

Reads agent-hooks/jev-guard.json (primary), deep-merges onto DEFAULTS.
Python 3.9 compatible: json stdlib only. tomllib branch guarded by try/except
for optional 3.11+ portability.

Public API:
  DEFAULTS         dict  — built-in safe config
  home()           -> pathlib.Path
  load_config()    -> dict   (never raises)
  tier_for_score() -> "deep"|"standard"|"quick"
  route_for_tier() -> dict
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
from typing import Literal

# ---------------------------------------------------------------------------
# DEFAULTS — mirrors jev-guard.json exactly
# ---------------------------------------------------------------------------
DEFAULTS: dict = {
    "routing": {
        "deep":     {"provider": "custom", "model": "anthropic--claude-4.8-opus",   "reasoning_effort": "high"},
        "standard": {"provider": "custom", "model": "anthropic--claude-4.6-sonnet", "reasoning_effort": "medium"},
        "quick":    {"provider": "custom", "model": "anthropic--claude-4.5-haiku",  "reasoning_effort": "minimal"},
        "thresholds": {"deep_min": 1.5, "standard_min": 0.5},
    },
    "caveman": {"enabled": True, "apply_to": ["subagent_brief", "subagent_report"]},
    "bulk_io": {
        "read_lines_min": 1500,
        "extract_urls_min": 4,
        "extract_char_limit_min": 30000,
        "write_chars_min": 16000,
        "chunk_block_p": 0.7,
    },
    "jev": {"model": "jev-latest", "timeout_seconds": 30, "fail_open": True},
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def home() -> pathlib.Path:
    """Return HERMES_HOME if set, else ~/.hermes."""
    raw = os.environ.get("HERMES_HOME", "")
    if raw:
        return pathlib.Path(raw)
    return pathlib.Path.home() / ".hermes"


def _deep_merge(base: dict, override: dict) -> dict:
    """Return a new dict: override's leaf values replace base's, recursively."""
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """
    Load jev-guard.json from home()/agent-hooks/jev-guard.json.
    Deep-merges onto DEFAULTS. On ANY error returns DEFAULTS. Never raises.
    """
    try:
        cfg_path = home() / "agent-hooks" / "jev-guard.json"
        if cfg_path.exists():
            text = cfg_path.read_text(encoding="utf-8")
            data = json.loads(text)
            return _deep_merge(DEFAULTS, data)

        # Optional: also try .toml on Python 3.11+ (tomllib in stdlib)
        toml_path = home() / "agent-hooks" / "jev-guard.toml"
        if toml_path.exists():
            try:
                import tomllib  # type: ignore  # Python 3.11+
                data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
                return _deep_merge(DEFAULTS, data)
            except ImportError:
                pass  # Not 3.11 — skip silently

    except Exception:  # noqa: BLE001 — intentional blanket catch
        pass

    return copy.deepcopy(DEFAULTS)


# ---------------------------------------------------------------------------
# tier_for_score / route_for_tier
# ---------------------------------------------------------------------------

def tier_for_score(
    score: float,
    cfg: dict,
) -> Literal["deep", "standard", "quick"]:
    """
    Map a quality/confidence score to a model tier.

    score >= deep_min    → "deep"
    score >= standard_min → "standard"
    else                  → "quick"
    """
    thresholds = cfg["routing"]["thresholds"]
    deep_min: float = thresholds["deep_min"]
    standard_min: float = thresholds["standard_min"]

    if score >= deep_min:
        return "deep"
    if score >= standard_min:
        return "standard"
    return "quick"


def route_for_tier(tier: str, cfg: dict) -> dict:
    """
    Return the routing dict for *tier* from cfg["routing"].
    Falls back to ["standard"] if tier is not present.
    """
    routing = cfg["routing"]
    if tier in routing and isinstance(routing[tier], dict):
        return copy.deepcopy(routing[tier])
    return copy.deepcopy(routing["standard"])
