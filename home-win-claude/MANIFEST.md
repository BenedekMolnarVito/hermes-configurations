# MANIFEST — home-win-claude

Generated: 2026-10-17
Target host: Windows 11, Claude Code 2.1.302, Pro subscription ($CLAUDE_HOME = ~/.claude)

## Top-level
```
install.ps1          importer (dry-run default; -Apply copies + merges; -Plugins installs plugins)
export.ps1           exporter (dry-run default; -Apply copies live owned files → config/; drift + secret scan)
merge_settings.py    idempotent settings.json merge (hooks appended by command, timeouts synced, dicts deep-merged)
settings_drift.py    read-only live-vs-template settings report
README.md            import / design / re-export notes
MANIFEST.md          this file
.gitignore           blocks live settings, backups, runtime logs
```

## config/ (copied into $CLAUDE_HOME)
```
CLAUDE.md                               guidelines + orchestration authorization + persistence protocol
settings.json.template                  env, hooks (SessionStart, StopFailure, PreToolUse:Agent, UserPromptSubmit), plugins
agents/scout.md                         haiku, read-only search/distill
agents/implementer.md                   sonnet, one scoped task
agents/reviewer.md                      opus, read-only verdict; chunks large diffs to chunk-reviewer
agents/chunk-reviewer.md                haiku, one diff chunk + XREF list
agents/synthesizer.md                   sonnet, reduce chunk reports
skills/orchestrate/SKILL.md             controller playbook
skills/agent-state/SKILL.md (+templates) .agent/ bootstrap
agent-hooks/agent_state_hooks.py        stdlib-only, fail-open (state, caveman, contract, JEV route/guard, skill-route)
agent-hooks/jevlib/                     JEV TypeSafe client + decisions (ported from home-win-hermes)
agent-hooks/jev-guard.json              JEV tiers, thresholds, pinned agents
skills/jev-{decisions,engineering,team-roles}/  JEV typed-question scripts
bin/claude-resumable.ps1                launcher with resumer channel
agent-hooks/mem0_recall.py              mem0 recall on every prompt (plugin core reuse, fail-open)
plugins/plugins.json                    marketplaces + plugins (resumer, caveman, mem0)
```

## Secrets
TYPESAFE_API_KEY: Windows user env only (export.ps1 scan fails if its value enters the bundle).
MEM0 API key: plugin sensitive option (cached in plugins/data/mem0-mem0-plugins/api-key, never exported).
None else. Pro subscription OAuth lives in ~/.claude/.credentials.json (never exported).
