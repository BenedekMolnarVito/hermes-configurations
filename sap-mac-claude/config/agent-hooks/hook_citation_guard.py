#!/usr/bin/env python3
"""
hook_citation_guard.py — pre_tool_call ADVISE hook for write_file|patch.

Reads one JSON object from stdin:
  {hook_event_name, tool_name, tool_input, session_id, cwd, profile, extra}

Writes AT MOST one JSON directive to stdout:
  {} (noop)  — this hook NEVER blocks; it is advisory only.

Behavior:
- Gate: tool_name in {write_file, patch}.
- Scan tool_input content for claim markers:
    • python import/from lines
    • path-like tokens (containing "/")
  Extract up to 5 {claim, source} pairs.
- No markers → noop "{}".
- decisions.citation_claims(claims) → for any contradicts@conf>0.8 OR
  absent-confidence → log_event("citation_warn", ...).
- Always returns "{}" regardless (ADVISE = telemetry only, never blocks).

Fail-open: any error → print "{}" and exit 0.

Python 3.9 compatible, stdlib only (plus jevlib).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
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
from jevlib.jev_client import UNAVAILABLE, log_event  # noqa: E402


# ---------------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------------

_IMPORT_RE = re.compile(r"^\s*(import\s+\S+|from\s+\S+\s+import\s+\S+)", re.MULTILINE)
_PATH_TOKEN_RE = re.compile(r"\S*\/\S+")


def _extract_claims(content: str, cwd: str) -> list:
    """
    Extract up to 5 {claim, source} dicts from content.

    Claim markers:
    - python import/from lines
    - path-like tokens (contain "/")

    For each marker, try to resolve the referenced file under cwd and read
    its content as the source; fall back to the surrounding line text.
    """
    claims: list = []

    # Collect candidate markers: import lines + path tokens
    markers: list = []

    for m in _IMPORT_RE.finditer(content):
        markers.append(("import", m.group(0).strip(), m.start()))

    for m in _PATH_TOKEN_RE.finditer(content):
        token = m.group(0)
        markers.append(("path", token, m.start()))

    # Deduplicate by text, preserve order
    seen: set = set()
    deduped: list = []
    for kind, text, pos in markers:
        key = (kind, text)
        if key not in seen:
            seen.add(key)
            deduped.append((kind, text, pos))

    for kind, text, pos in deduped[:5]:
        # Try to resolve source file
        source = text  # fallback = the marker text itself
        if kind == "path":
            candidate = pathlib.Path(text)
            if not candidate.is_absolute() and cwd:
                candidate = pathlib.Path(cwd) / text
            try:
                if candidate.is_file():
                    source = candidate.read_text(encoding="utf-8", errors="replace")[:500]
            except Exception:
                pass
        elif kind == "import":
            # Extract module name from "import foo" or "from foo import bar"
            m2 = re.match(r"(?:from\s+|import\s+)(\S+)", text)
            if m2:
                # Get surrounding context lines as source
                start = max(0, pos - 100)
                end = min(len(content), pos + 200)
                source = content[start:end]

        claims.append({"claim": text, "source": source})

    return claims


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
    tool_name = event.get("tool_name", "")
    if tool_name not in ("write_file", "patch"):
        print("{}")
        return

    tool_input = event.get("tool_input") or {}
    cwd = event.get("cwd", "")

    # Gather content to scan
    content_parts: list = []
    if "content" in tool_input:
        content_parts.append(str(tool_input["content"]))
    if "new_string" in tool_input:
        content_parts.append(str(tool_input["new_string"]))

    content = "\n".join(content_parts)
    claims = _extract_claims(content, cwd)

    if not claims:
        print("{}")
        return

    # Ask Jev about citation claims
    verdict = decisions.citation_claims(claims)

    # Regardless of verdict → this hook ALWAYS returns "{}" (ADVISE only)
    # But log a warning if any claim contradicts with high confidence or absent
    if verdict is not UNAVAILABLE:
        for i, result in verdict.items():
            v = result.get("verdict")
            conf = result.get("confidence", 0)
            if v == "contradicts" and conf > 0.8:
                log_event(
                    "citation_warn",
                    detail="contradicts@%.2f" % conf,
                    claim=claims[i]["claim"] if i < len(claims) else "",
                    tool=tool_name,
                )
            elif v == "contradicts" and conf == 0:
                # absent signal — also warn
                log_event(
                    "citation_warn",
                    detail="contradicts_absent_confidence",
                    claim=claims[i]["claim"] if i < len(claims) else "",
                    tool=tool_name,
                )

    print("{}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
