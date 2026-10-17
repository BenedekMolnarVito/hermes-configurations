#!/usr/bin/env python
"""
mem0_recall.py — UserPromptSubmit hook: mem0 recall on EVERY prompt.

The mem0 plugin (mem0@mem0-plugins) injects memories only on the first prompt of a
session; retain (capture + checkpoint/idle/pre-compact/session-end flush) is already
automatic in the plugin. This hook fills the recall gap by reusing the installed
plugin's own core (same API key cache, user_id, scope, and per-session dedupe, so a
memory is never injected twice in one session).

First prompt is left to the plugin: we only search when the session already has a
user prompt older than FIRST_PROMPT_GRACE seconds.

Fail-open: plugin missing, no key, network error → no output, exit 0.
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import sys

PLUGIN_ID = "mem0@mem0-plugins"
FIRST_PROMPT_GRACE = 3
CLAUDE_HOME = pathlib.Path(os.environ.get("CLAUDE_CONFIG_DIR") or pathlib.Path.home() / ".claude")


def plugin_core() -> pathlib.Path | None:
    installed = json.loads((CLAUDE_HOME / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
    entries = installed.get("plugins", {}).get(PLUGIN_ID) or []
    for entry in entries:
        core = pathlib.Path(entry.get("installPath", "")) / "core"
        if (core / "memory_core.py").is_file():
            return core
    return None


def plugin_env() -> None:
    # Plugin options reach only the plugin's own hooks; mirror them from settings.json.
    os.environ.setdefault("MEM0_CODE_DATA_DIR", str(CLAUDE_HOME / "plugins" / "data" / "mem0-mem0-plugins"))
    try:
        settings = json.loads((CLAUDE_HOME / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    options = settings.get("pluginConfigs", {}).get(PLUGIN_ID, {}).get("options", {})
    for name, value in options.items():
        if name != "api_key" and value not in (None, ""):
            os.environ.setdefault(f"CLAUDE_PLUGIN_OPTION_{name.upper()}", str(value))


def main() -> int:
    hook_input = json.load(sys.stdin)
    prompt = str(hook_input.get("prompt") or "").strip()
    session_id = str(hook_input.get("session_id") or "")
    if not session_id or len(prompt) < int(os.environ.get("MEM0_CODE_MIN_QUERY_CHARS", "20")):
        return 0
    core = plugin_core()
    if core is None:
        return 0
    plugin_env()
    sys.path.insert(0, str(core))
    import telemetry
    from memory_core import EvidenceStore, bounded, configure_harness, format_context, search_memories

    configure_harness("claude-code", data_dir_name="claude-code-plugin", source_tag="claude_code_plugin")
    telemetry.init(harness="claude-code", source_tag="CLAUDE_CODE_PLUGIN")
    store = EvidenceStore()
    try:
        repo = store.repo_for_session(session_id, hook_input.get("cwd"))
        cutoff = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(seconds=FIRST_PROMPT_GRACE)).isoformat()
        earlier = store.conn.execute(
            "SELECT 1 FROM events WHERE repo_id = ? AND session_id = ? AND kind = 'user_prompt'"
            " AND created_at < ? LIMIT 1",
            (repo.identity, session_id, cutoff),
        ).fetchone()
        if earlier is None:
            return 0
        result = search_memories(store, repo, session_id, bounded(prompt, 6000),
                                 operation="prompt-search", timeout=4)
        context = format_context(result.memories, "Mem0 recalled for this prompt:")
    finally:
        store.close()
    if context:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                 "additionalContext": context}}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
