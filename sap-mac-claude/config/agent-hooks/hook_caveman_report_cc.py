#!/usr/bin/env python3
"""
hook_caveman_report_cc.py — PostToolUse telegraphic compressor for Agent results.

Claude Code adapter of hook_caveman_report.py.
Fires after the Agent tool returns. Reads the tool response, compresses it
with caveman (strips filler words, preserves code/paths/numbers/quotes),
and injects the compressed version as additionalContext so the model reads
the compact form instead of re-processing the verbose report.

Only injects if compression actually shortens the result.
Fail-open: any error → print "{}" exit 0.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys


def _bootstrap_path() -> None:
    hermes_home = os.environ.get("HERMES_HOME", "")
    hooks_dir = (pathlib.Path(hermes_home) if hermes_home else pathlib.Path.home() / ".hermes") / "agent-hooks"
    s = str(hooks_dir)
    if s not in sys.path:
        sys.path.insert(0, s)


_bootstrap_path()

from jevlib import caveman, envload  # noqa: E402
envload.ensure()


def _extract_result_text(tool_response) -> str:
    """Pull text out of the Agent tool_response field."""
    if isinstance(tool_response, str):
        return tool_response
    if isinstance(tool_response, dict):
        # Claude Code wraps Agent results in {output: "..."}
        for key in ("output", "result", "content", "text"):
            val = tool_response.get(key)
            if isinstance(val, str) and val.strip():
                return val
        # content array (MCP-style)
        content = tool_response.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "\n".join(parts)
    return ""


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        print("{}")
        return

    try:
        _handle(payload)
    except Exception:
        print("{}")


def _handle(payload: dict) -> None:
    if payload.get("tool_name") != "Agent":
        print("{}")
        return

    if not caveman.enabled("subagent_report"):
        print("{}")
        return

    result_text = _extract_result_text(payload.get("tool_response"))
    if not result_text.strip():
        print("{}")
        return

    compressed = caveman.compress(result_text)

    # Only inject if we actually shortened it
    if not compressed or len(compressed) >= len(result_text):
        print("{}")
        return

    saved = len(result_text) - len(compressed)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"[Caveman-compressed subagent report ({saved} chars saved)]:\n{compressed}",
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
