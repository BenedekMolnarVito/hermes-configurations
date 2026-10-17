# home-win-claude

Importable **Claude Code** configuration for the personal Windows 11 workstation
(Claude Pro subscription). Windows sibling of [`sap-mac-claude/`](../sap-mac-claude/),
rebuilt Claude-Code-native and extended with the
[long-horizon playbook](../docs/superpowers/plans/claude-code-pro-long-horizon-playbook.md):

- **automatic multi-agent orchestration** — a standing authorization in `CLAUDE.md`,
  four model-tiered subagents, and an `orchestrate` skill;
- **rate-limit-proof persistence** — `.agent/` state files, a mandatory protocol in
  `CLAUDE.md`, a `SessionStart` hook that re-injects state, a `StopFailure` trace hook,
  and the `resumer` plugin to wake the session when the limit resets.

No secrets: this machine logs in with the Pro subscription (no gateway token).

## Layout

```
home-win-claude/
├── install.ps1          importer (dry-run by default; -Apply, -Plugins)
├── merge_settings.py    merges the template into a live settings.json (idempotent)
└── config/              copied into $CLAUDE_HOME (~/.claude)
    ├── CLAUDE.md                   guidelines + orchestration + persistence protocol
    ├── settings.json.template      hooks, env, plugins ({{CLAUDE_HOME}} filled on import)
    ├── agents/                     scout (haiku) · implementer (sonnet) · reviewer (opus) · synthesizer (sonnet)
    ├── skills/orchestrate/         controller playbook (dispatch, worktrees, map-reduce, multi-repo resume)
    ├── skills/agent-state/         creates .agent/ + templates
    ├── agent-hooks/agent_state_hooks.py   session-start · rate-limit · subagent-contract
    ├── bin/claude-resumable.ps1    launcher with the resumer channel enabled
    └── plugins/plugins.json        marketplaces + plugins to install
```

## Import

Prerequisites: Claude Code, a real `python` 3.9+ on PATH (not the Store `python3` stub), Node/npm, `gh` optional.

```powershell
cd home-win-claude
./install.ps1                    # preview
./install.ps1 -Apply -Plugins    # copy, merge settings.json, install resumer + caveman
```

Then **restart Claude Code** and check `/hooks`, `/agents`, `/plugin`, `/context`.

The importer only touches files this bundle owns; other skills/hooks (e.g. GitNexus) stay.
Changed files are backed up as `*.bak-<timestamp>`; `settings.json` is merged, never replaced.

## How the pieces fit

| Playbook item | Implemented as |
|---|---|
| 2.1 state files | `.agent/` per repo (git-excluded via `.git/info/exclude`), or `~/agent-work/<project>/` + `AGENT_STATE_DIR` for multi-repo — `agent-state` skill |
| 2.2 mandatory CLAUDE.md block | verbatim in `config/CLAUDE.md` |
| 2.5 SessionStart / StopFailure hooks | `agent_state_hooks.py` (Python, so it works in Git Bash *and* PowerShell; no-op outside repos with `.agent/`) |
| 2.2 rule 5 subagent return contract | enforced in code: `PreToolUse(Agent)` appends it to the prompt via `updatedInput` when `.agent/` exists |
| 2.6 resumer | `resumer@wong2-plugins` (reviewed: Node only, localhost-only control server with random token). Needs the channel flag → `claude-resumable.ps1` |
| 2.7 multi-repo protocol | `orchestrate` skill §1, §8 |
| 3 model routing | tiered agents (frontmatter `model` beats `CLAUDE_CODE_SUBAGENT_MODEL` since v2.1.251); `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` as the cheap default for untyped spawns |
| 4 cut input noise | CLAUDE.md context-hygiene rules (GitNexus first, filter output); Caveman in `manual` mode for chat (`/caveman` to opt in); inter-agent I/O always caveman (CLAUDE.md rule + `subagent-contract` hook) |
| JEV (TypeSafe) | `agent-hooks/jevlib` (stdlib, fail-open) + `jev-guard.json`. `PreToolUse(Agent)`: bulk-classify deny + JEV model/effort route for unpinned agents w/o `model`. `UserPromptSubmit`: JEV skill-route hint. Skills `jev-decisions`, `jev-engineering`, `jev-team-roles`. Key from user env `TYPESAFE_API_KEY`; `[jev-skip]` bypasses. Privacy: prompts ≥20 chars + unpinned Agent briefs are sent to api.typesafe.ai |
| chunked PR review | `reviewer` (opus, has `Agent`) decides: small → alone; large → haiku `chunk-reviewer` per chunk (high-risk/JEV risk ≥1.5 chunks stay opus) → opus cross-ref via `XREF:` lists, confirms every haiku Critical/Important |

## Deliberately not ported from sap-mac-claude

- **JEV hooks without a CC equivalent**: `browser_select` (CC browser tools carry no candidate list), `jira_classify` (no Jira tool here), `caveman_report` (CC hooks can't rewrite Agent output → caveman via prompt rule instead), `citation_guard` (telemetry-only in Hermes), mechanical `caveman.compress` of briefs (drops "to"/"and" → meaning loss).
- **Hindsight hooks, Jira MCP, SAP gateway/OTEL env, SAP marketplaces**: work-machine only.
- **The 60-skill catalog**: mostly Hermes-authored (`delegate_task`, `~/.hermes` paths). The orchestration ones are condensed into `orchestrate`; doc skills (pdf/docx/xlsx) are already provided by claude.ai here.

## Optional / user choices

- **RTK** output filtering (`./install.ps1 -Apply -Rtk`): winget-installs `rtk-ai.rtk` and runs `rtk init -g --auto-patch`, which adds a `PreToolUse:Bash` hook (`rtk hook claude`, rewrites e.g. `git status` → `rtk git status`) and `@RTK.md` to CLAUDE.md. Third-party binary — opt-in. Installed on this box 2026-10-17 (rtk 0.50.0). winget adds `%LOCALAPPDATA%\Microsoft\WinGet\Links` to user PATH; restart the parent app (VS Code/terminal), not just Claude Code, or the hook fails silently with `rtk: command not found`.
- `model`: kept `opus` by choice (strong controller). `/model opusplan` saves Pro quota if Opus usage hurts.
- Measure: `/usage` before/after, `npx ccusage blocks`, `/context`.

## Re-export after changing the live config

```powershell
$S = "$HOME/.claude"
Copy-Item $S/CLAUDE.md config/CLAUDE.md
Copy-Item $S/agents/{scout,implementer,reviewer,synthesizer}.md config/agents/
Copy-Item -Recurse -Force $S/skills/orchestrate, $S/skills/agent-state config/skills/
Copy-Item $S/agent-hooks/agent_state_hooks.py config/agent-hooks/
```
Hook/env changes: edit `config/settings.json.template` by hand (keep `{{CLAUDE_HOME}}`).
