# MANIFEST — sap-mac-harness

Generated: 2026-10-09T10:18:09Z
Source host: macOS (Hermes home $HERMES_HOME = ~/.hermes)

## Top-level
```
install.sh                   idempotent importer (dry-run default; --apply to copy)
README.md                    import/maintain instructions + machine-local caveats
MANIFEST.md                  this file
.gitignore                   blocks live .env / auth.json / secrets from git
```

## config/ (copied into $HERMES_HOME on import)
```
config.yaml                        main config (machine-local bits documented in README)
SOUL.md                            global agent persona/instructions
.env.template                      REDACTED env — 5 secret values stripped, settings kept
auth.json.template                 REDACTED provider auth — structure only, no tokens
memories/MEMORY.md                 agent long-term notes
memories/USER.md                   user profile
cron/jobs.json                     cron job DEFINITIONS (run history not included)
agent-hooks/                       9 shell hooks + jevlib + jev-guard.json (pycache/tests/_probes pruned)
scripts/                           poll_pr.py + watch_faa_pr259.sh (back the cron job)
skills/                            skill catalog incl .archive (curator machinery pruned)
```

## Counts
```
config files total : 353
config total size   : 4.0M
skills (SKILL.md)   : 91
agent-hooks (.py)   : 9
cron jobs           : 1
```

## Secrets redacted (MUST be set manually on import)
```
.env  : OPENROUTER_API_KEY, HERMES_CUSTOM_LOCALHOST_6655_API_KEY,
        HINDSIGHT_API_KEY, CUSTOM_API_KEY, TYPESAFE_API_KEY
auth.json : all provider tokens / credential_pool secrets (re-auth via hermes)
```
