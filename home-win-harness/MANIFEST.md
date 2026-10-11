# MANIFEST — home-win-harness

Generated: 2026-10-11
Source host: Windows 11 (Hermes home `$HERMES_HOME` = `%USERPROFILE%\AppData\Local\hermes`)
This folder: `home-win-harness/` (personal Windows-11 config; separate from `sap-mac-harness`)

## Top-level
```
install.sh            idempotent importer (dry-run default; --apply to copy)
README.md             import/maintain instructions + machine-local caveats
MANIFEST.md           this file
.gitignore            blocks live .env / auth.json / secrets / locks / OS noise
```

## config/ (copied into $HERMES_HOME on import)
```
config.yaml            main config (Windows paths; openrouter cloud provider; tier-router)
SOUL.md                global agent persona / standing instructions
.env.template          REDACTED env — 10 secret values stripped, settings kept
auth.json.template     REDACTED auth — structure + sha256 fingerprints only (no live tokens)
memories/MEMORY.md     agent long-term notes
memories/USER.md       user profile
cron/jobs.json         cron job DEFINITIONS (none — see "Deviations" below)
agent-hooks/           7 shell hooks + jevlib (6 .py) + jev-guard.json + README.md
skills/                skill catalog incl .archive (curator machinery pruned)
```

## Counts
```
config files total : 537
config total size  : 5,142,252 bytes (~4.9 MB)
skills (SKILL.md)  : 112
agent-hooks (.py)  : 13   (7 hooks + 6 in jevlib)
cron jobs          : 0   (1 excluded — see Deviations)
auth.json providers: 5   (sha256 fingerprints only: localhost:6655, copilot,
                          openrouter, custom:local-litellm, opencode-zen)
```

## Secrets redacted (MUST be set manually on import)
```
.env  : OPENROUTER_API_KEY, OPENCODE_ZEN_API_KEY, GITHUB_TOKEN,
        HERMES_CUSTOM_LOCALHOST_6655_API_KEY, HINDSIGHT_API_KEY, CUSTOM_API_KEY,
        TYPESAFE_API_KEY, SLACK_BOT_TOKEN, SLACK_APP_TOKEN, TELEGRAM_BOT_TOKEN
auth.json : NO live tokens — only non-reversible sha256 secret_fingerprints
            are retained (per CONTRIBUTING rule), plus provider metadata.
            Re-authenticate every provider via `hermes` on import (OAuth doesn't transfer).
```

## Deviations from the live source config (de-SAP'd for the personal config)
```
cron/jobs.json : excluded the "PR 259 re-review watcher" job (SAP/FAA-specific,
                  targets github.tools.sap, and non-functional on this Windows
                  machine — backing script watch_faa_pr259.sh was not ported).
config.yaml    : removed the dead hook matcher `mcp__sap_jira__jira_create_issue`
                  (targets SAP's internal Jira MCP, which is not configured here —
                  mcp_servers is empty). Reworded the header caveat that named it.
                  hook_jira_classify.py is retained in agent-hooks/ (unwired).
```
Everything else is an unmodified copy of the live `$HERMES_HOME` (secrets excepted).

## Config isolation (this config must never collide with sap-mac-harness)
This folder and `sap-mac-harness/` are fully independent: separate top-level
trees, separate secret sets, separate provider auth, separate memory bank.
They must be imported into **separate** `$HERMES_HOME` locations (or separate
Hermes profiles via `hermes profiles`) — never merged into one home. See
CONTRIBUTING.md "Config isolation".
