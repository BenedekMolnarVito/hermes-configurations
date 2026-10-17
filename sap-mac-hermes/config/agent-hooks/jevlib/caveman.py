"""
jevlib/caveman.py — Telegraphic compressor + enabled() gating.

stdlib only: os, re
Python 3.9 compatible.

Public API
----------
compress(text) -> str   Compress prose; protect code/paths/numbers/quotes verbatim.
enabled(kind)  -> bool  Check if caveman compression applies to the given kind.
"""
from __future__ import annotations

import os
import re

from . import config

# ---------------------------------------------------------------------------
# _PROTECT — spans to keep verbatim (single alternation, re.DOTALL)
# ---------------------------------------------------------------------------
# Order matters: longer/more-specific patterns before shorter ones.
_PROTECT = re.compile(
    r"```.*?```"                          # fenced code blocks
    r"|`[^`]*`"                            # inline backtick
    r'|"[^"]*"'                            # double-quoted strings
    r"|'[^']*'"                            # single-quoted strings
    r"|https?://\S+"                       # URLs
    r"|[\w./~-]+/[\w./~-]+"               # file paths containing a slash
    r"|\b[A-Z][A-Z0-9_]{2,}\b"            # ALLCAPS identifiers
    r"|\b\d[\d.,]*\b",                     # numbers
    re.DOTALL,
)

# ---------------------------------------------------------------------------
# _FILLER — standalone filler words / phrases to delete from prose gaps
# ---------------------------------------------------------------------------
_FILLER = re.compile(
    r"\bgoing\s+to\b"                      # "going to" (compound — before singles)
    r"|and\s+then\b"                       # "and then" (compound)
    r"|\b(?:the|a|an|is|are|was|were|be|been|being|to|of|that|this|please|then|so|will|just|and)\b",
    re.IGNORECASE,
)

# Collapse multiple spaces/tabs into one
_SPACES = re.compile(r"[ \t]{2,}")
# Tidy ", " where a comma follows a space left by removed filler
_SPACE_COMMA = re.compile(r"\s+,")


def compress(text) -> str:
    """
    Compress prose, protecting specific spans verbatim.

    Protected: fenced blocks, inline backtick, quoted strings, URLs,
    file paths, ALLCAPS identifiers, numbers.

    Prose gaps: drop _FILLER words, collapse whitespace.

    Empty/None → return as-is.
    """
    if not text:
        return text

    parts: list[str] = []
    last = 0

    for m in _PROTECT.finditer(text):
        start, end = m.start(), m.end()
        # Process the prose gap before this protected span
        gap = text[last:start]
        gap = _FILLER.sub(" ", gap)
        gap = _SPACES.sub(" ", gap)
        parts.append(gap)
        # Keep the protected span unchanged
        parts.append(m.group())
        last = end

    # Trailing prose gap
    tail = text[last:]
    tail = _FILLER.sub(" ", tail)
    tail = _SPACES.sub(" ", tail)
    parts.append(tail)

    result = "".join(parts)
    result = _SPACE_COMMA.sub(",", result)
    result = _SPACES.sub(" ", result)
    return result.strip()


# ---------------------------------------------------------------------------
# enabled
# ---------------------------------------------------------------------------

def enabled(kind: str) -> bool:
    """
    Check if caveman compression applies to the given kind.

    JEVGUARD_CAVEMAN env var (case-insensitive):
      "off"       → False for everything.
      "reasoning" → kind=="quick_turn_reasoning" returns True; others use cfg.
      (absent/other) → cfg["caveman"]["enabled"] AND kind in cfg["caveman"]["apply_to"].

    "quick_turn_reasoning" is OFF by default (only True when env=="reasoning").
    """
    env_val = os.environ.get("JEVGUARD_CAVEMAN", "").lower()

    if env_val == "off":
        return False

    if kind == "quick_turn_reasoning":
        return env_val == "reasoning"

    # Normal kinds: consult config
    cfg = config.load_config()
    caveman_cfg = cfg.get("caveman", {})
    return bool(caveman_cfg.get("enabled", False)) and kind in caveman_cfg.get("apply_to", [])
