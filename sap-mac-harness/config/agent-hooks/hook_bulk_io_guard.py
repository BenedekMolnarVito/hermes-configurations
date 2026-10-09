#!/usr/bin/env python3
"""
hook_bulk_io_guard.py — pre_tool_call HARD-BLOCK for bulky read/write/extract
that should be CHUNKED across subagents + reassembled by a synthesis agent.

Complements hook_batch_guard.py: that one blocks bulk CLASSIFY/RANK/TRIAGE jobs
(route to jev-decisions). THIS one blocks bulky DATA I/O by VOLUME — a read /
web_extract / write large enough to flood the long-running orchestrator context
— and forces the chunk-and-synthesize path (skill: chunked-bulk-io-synthesis).

Reads one JSON object from stdin:
  {hook_event_name, tool_name, tool_input, session_id, cwd, profile, extra}

Writes AT MOST one JSON directive to stdout:
  {} (noop)
  {"action": "block", "message": "..."}

Behavior:
- Gate: tool_name in {read_file, web_extract, write_file}.
- LOCAL PREFILTER first (no Jev call): build a compact, NON-content io_shape and
  decide if the call is bulky enough to be worth a judgement:
    read_file   : limit >= READ_LINES_MIN                       (default 1500)
    web_extract : len(urls) >= EXTRACT_URLS_MIN (default 4)  OR  char_limit high
    write_file  : len(content) >= WRITE_CHARS_MIN              (default 16000)
  If prefilter fails → noop "{}" immediately (Jev not called).
- Only if prefilter matches → call decisions.is_bulk_io(tool_name, io_shape).
  is_bulk_io sends ONLY sizes/counts/path-hints to Jev, never raw content.
  If chunk_p >= CHUNK_BLOCK_P (default 0.7) → block.
  Else → noop "{}".
- Escape hatch: JEVGUARD_BULK_IO=off → always noop (never block).

Fail-open: no API key / Jev down / any error → print "{}" and exit 0.

Thresholds come from jev-guard.json "bulk_io" (deep-merged onto DEFAULTS in
jevlib/config.py), so they are tunable with zero code change.

Python 3.9 compatible, stdlib only (plus jevlib).
"""
from __future__ import annotations

import json
import os
import pathlib
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

from jevlib import config, decisions  # noqa: E402
from jevlib import envload  # noqa: E402
envload.ensure()
from jevlib.jev_client import UNAVAILABLE, log_event  # noqa: E402


_GATE_TOOLS = ("read_file", "web_extract", "write_file")

# Fallback thresholds if the config block is absent (mirror of config.DEFAULTS).
_FALLBACK = {
    "read_lines_min": 1500,
    "extract_urls_min": 4,
    "extract_char_limit_min": 30000,
    "write_chars_min": 16000,
    "chunk_block_p": 0.7,
}


def _thresholds() -> dict:
    cfg = config.load_config()
    block = dict(_FALLBACK)
    try:
        block.update(cfg.get("bulk_io", {}) or {})
    except Exception:
        pass
    return block


def _path_hint(path: str) -> str:
    """Return a short, non-sensitive path hint (basename + one parent)."""
    if not path:
        return ""
    try:
        p = pathlib.PurePath(path)
        parts = p.parts[-2:]
        return "/".join(parts)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Prefilter — build a compact io_shape; return None if NOT bulky.
# ---------------------------------------------------------------------------

def _io_shape(tool_name: str, tool_input: dict, th: dict):
    """
    Return a compact NON-content io_shape dict if the call is bulky enough to
    judge, else None. Never includes raw content — only sizes/counts/hints.
    """
    if not isinstance(tool_input, dict):
        return None

    if tool_name == "read_file":
        limit = tool_input.get("limit")
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 0
        if limit >= th["read_lines_min"]:
            return {
                "op": "read",
                "lines": limit,
                "path_hint": _path_hint(str(tool_input.get("path", ""))),
            }
        return None

    if tool_name == "web_extract":
        urls = tool_input.get("urls")
        url_count = len(urls) if isinstance(urls, list) else 0
        char_limit = tool_input.get("char_limit")
        try:
            char_limit = int(char_limit)
        except (TypeError, ValueError):
            char_limit = 0
        if url_count >= th["extract_urls_min"] or char_limit >= th["extract_char_limit_min"]:
            return {"op": "extract", "url_count": url_count, "char_limit": char_limit}
        return None

    if tool_name == "write_file":
        content = tool_input.get("content")
        n = len(content) if isinstance(content, str) else 0
        if n >= th["write_chars_min"]:
            return {
                "op": "write",
                "content_chars": n,
                "path_hint": _path_hint(str(tool_input.get("path", ""))),
            }
        return None

    return None


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
    # Explicit off switch
    if os.environ.get("JEVGUARD_BULK_IO", "").lower() == "off":
        print("{}")
        return

    tool_name = event.get("tool_name", "")
    if tool_name not in _GATE_TOOLS:
        print("{}")
        return

    tool_input = event.get("tool_input") or {}
    th = _thresholds()

    io_shape = _io_shape(tool_name, tool_input, th)
    if io_shape is None:
        # Not bulky → noop immediately, no Jev call.
        print("{}")
        return

    verdict = decisions.is_bulk_io(tool_name, io_shape)
    if verdict is UNAVAILABLE:
        print("{}")
        return

    chunk_p = verdict.get("chunk_p", 0)
    if chunk_p >= th["chunk_block_p"]:
        log_event(
            "bulk_io_block",
            tool=tool_name,
            op=io_shape.get("op"),
            chunk_p=round(float(chunk_p), 3),
        )
        directive = {
            "action": "block",
            "message": (
                "This bulky %s (%s) would flood the orchestrator context. "
                "Do NOT run it directly. Load the chunked-bulk-io-synthesis "
                "skill: split the work into chunks, hand each to a subagent "
                "(delegate_task) that returns only a distilled result, and have "
                "ONE synthesis agent reassemble the chunks into the whole. "
                "Set JEVGUARD_BULK_IO=off to bypass if you genuinely need this "
                "content verbatim in your own context."
                % (tool_name, io_shape.get("op"))
            ),
        }
        print(json.dumps(directive))
        return

    print("{}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
