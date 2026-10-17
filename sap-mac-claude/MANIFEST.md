# MANIFEST — sap-mac-claude

Generated: 2026-10-16
Source host: macOS (Claude Code home $CLAUDE_HOME = ~/.claude)

## Top-level
```
install.sh                   idempotent importer (dry-run default; --apply to copy)
README.md                    import/maintain instructions + machine-local caveats
MANIFEST.md                  this file
.gitignore                   blocks live settings.json / settings.local.json / secrets from git
```

## config/ (copied into $CLAUDE_HOME on import)
```
CLAUDE.md                          global behavioral guidelines (user instructions)
settings.json.template             REDACTED main settings — 3 secret values stripped, hook paths
                                   rewritten to ~/.claude/agent-hooks (self-contained)
settings.local.json.template       project permission allowlist (no secrets)
memory/MEMORY.md                   memory index
memory/reference_local_repos.md    long-term note: local repo paths
agent-hooks/                       7 Claude-Code hooks (hook_*_cc.py, hook_bulk_io_guard.py,
                                   hook_citation_guard.py, hook_delegate_route.py) + jevlib
skills/                            skill catalog (60 SKILL.md across 11 categories)
plugins/known_marketplaces.json    marketplace sources (install paths/timestamps stripped)
plugins/installed_plugins.json     plugin names + versions (install paths/timestamps stripped)
```

What is **deliberately NOT included** (machine-local, regenerated, or sensitive):
session history (`history.jsonl`, `sessions/`, `projects/*/`), caches (`cache/`,
`paste-cache/`, `plugins/cache/`), logs/daemon state (`daemon*`, `*.lock`),
`file-history/`, `shell-snapshots/`, `backups/`, `ide/`, `downloads/`, `tasks/`,
`jobs/`, `session-env/`, and the cloned plugin marketplace contents (re-fetched
by `/plugin marketplace add` on import).

## Counts
```
config files total : 239
config total size   : 3.0M
skills (SKILL.md)   : 60
agent-hooks (.py)   : 14   (7 hooks + jevlib modules)
memory files        : 2
```

## Secrets redacted (MUST be set manually on import)
```
settings.json : ANTHROPIC_AUTH_TOKEN, TYPESAFE_API_KEY,
                JIRA_PERSONAL_TOKEN (top-level env AND mcpServers.jira.env)
```
`settings.local.json` holds only a permission allowlist — no secrets.
