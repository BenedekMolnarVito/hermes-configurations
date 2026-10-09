#!/usr/bin/env python3
"""
hook_hindsight_condense.py — transform_tool_result hook for hindsight_recall.

Condenses the result of EXPLICIT hindsight_recall tool calls:
  dedup (Jaccard) -> JEV NOUL rerank -> caveman compress.

Emits the condensed string on stdout (raw, no JSON wrapper).
Emitting nothing (empty stdout) signals "leave result unchanged".

The auto-prefetch recall path is handled separately by the
hindsight-condense-patch plugin (monkey-patch of _do_recall).

Fail-open: any error -> emit nothing, exit 0.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys


def _hermes_home() -> pathlib.Path:
    raw = os.environ.get("HERMES_HOME", "")
    if raw:
        return pathlib.Path(raw)
    return pathlib.Path.home() / ".hermes"


def main() -> None:
    hooks_dir = str(_hermes_home() / "agent-hooks")
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)

    raw = sys.stdin.buffer.read()
    payload = json.loads(raw)

    if payload.get("hook_event_name") != "transform_tool_result":
        return
    # Match hindsight recall + reflect tools (both inject memory text).
    tool_name = payload.get("tool_name") or ""
    if tool_name not in ("hindsight_recall", "hindsight_reflect"):
        return

    extra = payload.get("extra") or {}
    result = extra.get("result") or ""
    if not result or not result.strip():
        return

    # Try to recover the query from the tool arguments for JEV reranking.
    # The arguments may live under extra["arguments"] or extra["args"].
    query = ""
    args = extra.get("arguments") or extra.get("args") or {}
    if isinstance(args, dict):
        query = args.get("query") or ""

    from jevlib.hindsight_condense import condense_memories

    condensed = condense_memories(result, query=query, max_memories=15)

    # Only emit if we actually shortened it; otherwise leave unchanged.
    if condensed and len(condensed) < len(result):
        sys.stdout.write(condensed)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        pass  # fail-open: emit nothing, exit 0
