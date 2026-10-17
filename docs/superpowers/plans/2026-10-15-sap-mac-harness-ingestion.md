# sap-mac-hermes Hermes Configuration Ingestion

**Goal:** Wire JEV/TypeSafe decision hooks and copy generic skills from sap-mac-hermes into Claude Code's user-scoped settings.

**Architecture:** All changes are user-scoped (`~/.claude/settings.json` and `~/.claude/skills/`). Hook scripts live at `~/.hermes/agent-hooks/` (pre-existing Hermes install). A thin Claude Code adapter wraps the Hermes `UserPromptSubmit` payload format mismatch.

**Key components:**
- `~/.claude/settings.json` — env vars (TYPESAFE_API_KEY, HERMES_HOME) + hooks section
- `~/.hermes/agent-hooks/hook_skill_route_cc.py` — Claude Code adapter for skill routing
- `~/.claude/skills/` — 58 non-FAA skills copied from sap-mac-hermes

---

## What Was Done

### 1. Env Vars Added to `~/.claude/settings.json`

```json
"env": {
  "TYPESAFE_API_KEY": "<108-char key from ~/.hermes/.env>",
  "HERMES_HOME": "/Users/C5418860/.hermes"
}
```

`HERMES_HOME` ensures hook scripts find `jevlib/` and `~/.hermes/.env` regardless of CWD.
`TYPESAFE_API_KEY` is available in Claude Code subprocess hooks (hooks don't inherit `~/.hermes/.env`).

### 2. JEV Hooks Wired in `~/.claude/settings.json`

```json
"hooks": {
  "PreToolUse": [
    { "matcher": "Task",       "command": "hook_delegate_route.py",  "timeout": 30 },
    { "matcher": "Read|WebFetch", "command": "hook_bulk_io_guard.py", "timeout": 30 },
    { "matcher": "Write|Edit", "command": "hook_citation_guard.py",  "timeout": 20 }
  ],
  "UserPromptSubmit": [
    { "command": "hook_skill_route_cc.py", "timeout": 15 }
  ]
}
```

Hook scripts at `~/.hermes/agent-hooks/`. All fail-open (return `{}` on any error).

**Hook behaviors:**
- `hook_delegate_route.py` — JEV classifies subtask complexity → injects model tier (deep/standard/quick) into Task tool calls
- `hook_bulk_io_guard.py` — detects large read/write operations, advises chunking
- `hook_citation_guard.py` — verifies citation claims in file writes via JEV
- `hook_skill_route_cc.py` — routes user prompt to best-matching skill if confidence ≥ 0.30

### 3. Claude Code Adapter: `hook_skill_route_cc.py`

The Hermes `hook_skill_route.py` guards on `hook_event_name == "pre_llm_call"` and extracts `extra.user_message`. Claude Code's `UserPromptSubmit` sends `prompt` at top level with no `hook_event_name`.

The adapter at `~/.hermes/agent-hooks/hook_skill_route_cc.py`:
- Reads `prompt` from top-level payload
- Falls back to last user turn in `transcript` array
- Calls the same `decisions.skill_route()` function directly
- Returns `hookSpecificOutput.additionalContext` (Claude Code's format for injecting context)

### 4. Skills Copied to `~/.claude/skills/`

58 skills across 10 categories (FAA-specific and SAP-SSO excluded):

| Category | Count |
|---|---|
| autonomous-ai-agents | 7 |
| software-development | 20 |
| jev-decisions + jev-engineering | 2 |
| github | 7 |
| research | 4 |
| productivity | 9 |
| mlops | 6 |
| devops | 1 |
| web | 2 |

Key skills:
- `subagent-execution-orchestration` — hub-and-spoke orchestration procedure
- `synthesis-agent` — condense subagent batches via handoff packet
- `parallel-review-subagents` — fan-out review patterns
- `typesafe-ai` — building with JEV/System One model
- `jev-hermes-decision-hooks` — JEV hook design patterns
- `agentic-architecture-design`, `codebase-inspection`, `change-integration-analysis`
- `simplify-code`, `spike`, `verify-pr`, `plan`

## How JEV Hook Routing Works

```
User prompt submitted
  → hook_skill_route_cc.py (UserPromptSubmit)
      → decisions.skill_route(prompt, ~/.claude/skills/*/SKILL.md)
      → JEV returns {skill: "...", confidence: 0.0-1.0}
      → if confidence >= 0.30: inject "Load skill X before acting" as additionalContext

Task tool called (delegate_task / Agent)
  → hook_delegate_route.py (PreToolUse on Task)
      → decisions.complexity_tier(subtask_goals)
      → JEV returns tier per goal (quick/standard/deep)
      → injects model override into task input

Read/WebFetch
  → hook_bulk_io_guard.py
      → checks line count / URL count / char count
      → if above thresholds: injects chunking advisory

Write/Edit
  → hook_citation_guard.py
      → checks written content for citation claims
      → if suspicious: injects verification advisory
```

## Notes

- `hook_jira_classify.py` not wired — Claude Code uses `mcp__jira__*` tool names, not `mcp__sap_jira__*`. Can be added when the Jira MCP tool name is confirmed.
- `hook_caveman_report.py` and `hook_hindsight_condense.py` not wired — these are Hermes-specific (PostToolUse for delegate_task and hindsight_recall; no equivalent in Claude Code yet).
- `hook_batch_guard.py` not wired — targets `delegate_task|web_extract` but web_extract is a Hermes tool; Claude Code uses WebFetch. The bulk_io_guard covers WebFetch.
