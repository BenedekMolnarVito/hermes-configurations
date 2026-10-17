# MANIFEST — home-win-claude

Generated: 2026-10-17
Target host: Windows 11, Claude Code 2.1.302, Pro subscription ($CLAUDE_HOME = ~/.claude)

## Top-level
```
install.ps1          importer (dry-run default; -Apply copies + merges; -Plugins installs plugins)
merge_settings.py    idempotent settings.json merge (hooks appended by command, dicts deep-merged)
README.md            import / design / re-export notes
MANIFEST.md          this file
.gitignore           blocks live settings, backups, runtime logs
```

## config/ (copied into $CLAUDE_HOME)
```
CLAUDE.md                               guidelines + orchestration authorization + persistence protocol
settings.json.template                  env, hooks (SessionStart, StopFailure, PreToolUse:Agent), plugins
agents/scout.md                         haiku, read-only search/distill
agents/implementer.md                   sonnet, one scoped task
agents/reviewer.md                      opus, read-only verdict
agents/synthesizer.md                   sonnet, reduce chunk reports
skills/orchestrate/SKILL.md             controller playbook
skills/agent-state/SKILL.md (+templates) .agent/ bootstrap
agent-hooks/agent_state_hooks.py        stdlib-only, fail-open
bin/claude-resumable.ps1                launcher with resumer channel
plugins/plugins.json                    marketplaces + plugins (resumer, caveman)
```

## Secrets
None. Pro subscription OAuth lives in ~/.claude/.credentials.json (never exported).
