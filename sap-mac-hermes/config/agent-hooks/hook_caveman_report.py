#!/usr/bin/env python3
"""
hook_caveman_report.py — transform_tool_result hook for delegate_task results.

Compresses subagent reports with caveman compression when enabled.
Emits the compressed string on stdout (raw, no JSON wrapper).
Emitting nothing (empty stdout) signals "leave result unchanged".

Fail-open: any error → emit nothing, exit 0.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys


def _hermes_home() -> pathlib.Path:
    """Return HERMES_HOME env if set, else ~/.hermes."""
    raw = os.environ.get("HERMES_HOME", "")
    if raw:
        return pathlib.Path(raw)
    return pathlib.Path.home() / ".hermes"


def main() -> None:
    # Wire jevlib onto sys.path from the agent-hooks dir.
    hooks_dir = str(_hermes_home() / "agent-hooks")
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)

    from jevlib import caveman  # noqa: PLC0415 — intentional deferred import

    # Read and parse stdin JSON.
    raw = sys.stdin.buffer.read()
    payload = json.loads(raw)

    # Only act on transform_tool_result for delegate_task.
    if payload.get("hook_event_name") != "transform_tool_result":
        return
    if payload.get("tool_name") != "delegate_task":
        return

    # Extract result text; blank → no-op.
    result: str = (payload.get("extra") or {}).get("result") or ""
    if not result:
        return

    # Gate on caveman enabled for subagent_report.
    if not caveman.enabled("subagent_report"):
        return

    # Compress and emit.
    compressed = caveman.compress(result)
    sys.stdout.write(compressed)

    # -----------------------------------------------------------------------
    # Defensive effort-restore: if Task 4's marker exists, restore the prior
    # reasoning_effort and remove the marker.  Best-effort only.
    # Skipped when JEVGUARD_SKIP_CONFIG_WRITE=1 (tests / CI).
    # -----------------------------------------------------------------------
    if os.environ.get("JEVGUARD_SKIP_CONFIG_WRITE") != "1":
        try:
            marker = _hermes_home() / "cache" / "jevguard_effort_restore"
            if marker.exists():
                prior_effort = marker.read_text(encoding="utf-8").strip()
                if prior_effort:
                    subprocess.run(
                        ["hermes", "config", "set", "delegation.reasoning_effort", prior_effort],
                        timeout=10,
                        capture_output=True,
                    )
                marker.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass  # best-effort — never surface errors here


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        pass  # fail-open: emit nothing, exit 0
