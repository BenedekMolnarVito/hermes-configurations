# sap-mac-hermes

A **self-contained, importable export of a complete Hermes Agent configuration**,
captured from a macOS workstation. Drop this folder onto a new machine, run the
importer, fill in the secrets, and you have the same Hermes configuration: model
routing, persona, memory, skills, agent-hooks, cron jobs, and MCP wiring.

This folder is independent of any sibling folders in this repo — it owns only
`sap-mac-hermes/` and copies nothing from outside it.

> **Secrets are redacted.** No live API keys or auth tokens are stored here.
> Every stripped value is replaced with `__SET_ME_ON_IMPORT__` and must be
> filled in manually after import (see [Secrets](#secrets-must-be-filled-in-manually)).

---

## Layout

```
sap-mac-hermes/
├── README.md            ← you are here
├── MANIFEST.md          ← file inventory + counts
├── install.sh           ← idempotent importer (dry-run by default)
├── .gitignore           ← prevents live .env / auth.json from being committed
└── config/              ← the actual Hermes config (copied into $HERMES_HOME)
    ├── config.yaml              main configuration
    ├── SOUL.md                  global agent persona / standing instructions
    ├── .env.template            REDACTED env vars (settings kept, secrets stripped)
    ├── auth.json.template       REDACTED provider auth (structure only, no tokens)
    ├── memories/
    │   ├── MEMORY.md            agent long-term notes
    │   └── USER.md              user profile
    ├── cron/
    │   └── jobs.json            cron job DEFINITIONS (run history excluded)
    ├── agent-hooks/             9 shell hooks + jevlib + jev-guard.json
    ├── scripts/                 scripts the cron job depends on
    └── skills/                  skill catalog (curator machinery pruned, .archive kept)
```

What is **deliberately NOT included** (machine-local, regenerated, or sensitive):
session history (`state.db`), caches, logs, browser profiles, runtime state
(`gateway_state.json`, pids, locks), the `hermes-agent` codebase itself, cron
run-history (`executions.db`), and the skills curator machinery
(`.curator_*`, `.hub`, `.locks`, `.bundled_manifest`, per-skill `.usage.json`).

---

## Quick start (import onto a new machine)

Prerequisite: Hermes Agent is installed and has been run once (so `$HERMES_HOME`,
default `~/.hermes`, exists).

```bash
cd sap-mac-hermes

# 1. Preview exactly what will be copied (changes nothing):
./install.sh

# 2. Apply the import:
./install.sh --apply

# ...or target a non-default Hermes home:
HERMES_HOME=/custom/.hermes ./install.sh --apply
```

The importer is **non-destructive**:
- plain config files that already exist are backed up to `*.bak-<timestamp>`
  before being overwritten;
- a live `.env` / `auth.json` on the target is **never** touched — if absent,
  the redacted template is seeded there for you to fill in.

Then follow the printed checklist (and the sections below).

---

## Secrets (must be filled in manually)

Nothing secret is stored in this repo. After import, edit the two files Hermes
actually reads and replace every `__SET_ME_ON_IMPORT__`:

### `$HERMES_HOME/.env`
| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter model access |
| `HERMES_CUSTOM_LOCALHOST_6655_API_KEY` | key for the local LiteLLM proxy (default + all model tiers) |
| `HINDSIGHT_API_KEY` | Hindsight long-term memory backend |
| `CUSTOM_API_KEY` | dummy key for the local Ollama provider (any non-empty value; Ollama ignores it) |
| `TYPESAFE_API_KEY` | TypeSafe / JEV (used by jev-* skills and the jev-guard hook) |

All other `.env` entries are non-secret settings and are kept at their real
values. The large commented block is the stock Hermes `.env` reference — harmless.

### `$HERMES_HOME/auth.json`
Structure only — all provider tokens were stripped. Do **not** hand-edit tokens
in; instead run `hermes` and re-authenticate each provider. OAuth tokens do not
transfer between machines.

---

## Machine-local assumptions (this config was captured on macOS)

The config references services and paths specific to the source machine. On a
new box, make sure these exist or adjust them:

1. **LiteLLM proxy — `http://localhost:6655/litellm/v1`**
   This is the **default provider and all three model tiers** (deep =
   `anthropic--claude-4.8-opus`, standard = `...4.6-sonnet`, quick =
   `...4.5-haiku`), plus the `delegation` model. If no LiteLLM proxy runs on
   `:6655` on the new machine, Hermes cannot reach any model. Either start the
   same proxy, or switch to a direct cloud provider with `hermes model`.

2. **Ollama — `http://localhost:11434/v1`** (`custom_providers` → "Hermes MAC",
   model `gemma4:31b`). Only needed if you use that provider; otherwise ignore.

3. **`skills.trusted_project_dirs`** contains a mac path
   (`/Users/C5418860/temp/treasury-scribe`). Edit or clear it in `config.yaml`
   for the new machine (Windows accepts forward-slash paths like `C:/Users/...`).

4. **Agent-hooks** are referenced in `config.yaml` as `~/.hermes/agent-hooks/*.py`.
   `~` expands on every OS. On Windows, Hermes auto-prepends the Python
   interpreter for a bare `.py` hook **provided Python is on PATH** — a hook that
   errors "cannot be run directly on Windows" means Python isn't found, not that
   the hook is broken. The shell-hooks **allowlist is machine-local and is not
   shipped**: Hermes will ask you to re-approve each hook once.

5. **`memory.provider: hindsight`** needs the `hindsight` plugin installed on the
   target, its env vars present (`HINDSIGHT_API_URL`, `HINDSIGHT_BANK_ID`,
   `HINDSIGHT_API_KEY`), and the backend reachable. `HINDSIGHT_BANK_ID` is
   `sap-mac-hermes` — change it if you want a separate memory bank on the new box.

6. **MCP server `sap-jira`** (`https://mcp.jira.tools.sap/mcp`, `auth: oauth`)
   re-authenticates on first use on the new machine.

7. **Cron job** "PR 259 re-review watcher" runs `scripts/watch_faa_pr259.sh`
   (which calls `scripts/poll_pr.py`). It is FAA/SAP-GitHub-specific and expects
   `gh` configured for `github.tools.sap`. Disable or delete it with
   `hermes cronjob` if not wanted on the new machine.

---

## Plugins

`config.yaml` enables these plugins — install them on the target before relying
on the config:

- `superpowers`
- `hindsight` (+ `hindsight-condense-patch`)
- `delegate-pertask-model-patch`

(`probe-effort-observer` is listed as disabled.) After installing, run
`hermes doctor` to confirm config, providers, and plugins are green.

---

## Maintaining this export (re-export after you change your live config)

To refresh this folder from the current live `~/.hermes`, re-run the same
curation the export used. From inside `sap-mac-hermes/`:

```bash
SRC="${HERMES_HOME:-$HOME/.hermes}"

# plain config
cp "$SRC/config.yaml" config/config.yaml
cp "$SRC/SOUL.md"     config/SOUL.md
cp "$SRC/memories/MEMORY.md" "$SRC/memories/USER.md" config/memories/
cp "$SRC/cron/jobs.json" config/cron/jobs.json

# agent-hooks (prune pycache/tests/_probes)
rsync -a --exclude='__pycache__' --exclude='_probes/' --exclude='tests/' \
  "$SRC/agent-hooks/" config/agent-hooks/

# skills (prune curator machinery, keep .archive)
rsync -a --exclude='.curator_backups/' --exclude='.curator_ledger.jsonl' \
  --exclude='.curator_state' --exclude='.bundled_manifest' --exclude='.locks/' \
  --exclude='.hub/' --exclude='__pycache__/' --exclude='.usage.json' \
  --exclude='.usage.json.lock' --exclude='.DS_Store' \
  "$SRC/skills/" config/skills/
```

Then **re-redact secrets** — never copy the live `.env` / `auth.json` in:
regenerate `config/.env.template` (strip the 5 secret values above, keep
settings) and `config/auth.json.template` (structure only). The `.gitignore`
blocks a live `.env` / `auth.json` from being committed as a safety net, but
always re-check with:

```bash
git -C .. status
grep -rn '__SET_ME_ON_IMPORT__' config/.env.template config/auth.json.template
```

before committing, to confirm the secrets are placeholders, not real values.

---

## Honesty note

The import flow is validated as far as it can be from the source machine: the
importer was dry-run and `--apply`-tested into a scratch Hermes home (354 files
copied, `config.yaml` parses, secrets seeded as placeholders, re-run is
idempotent and non-destructive). Target-side steps — plugin install, hook
re-approval, provider re-auth, MCP OAuth, and whether `localhost:6655`/`:11434`
services exist — are **guided, not executed here**, and must be completed on the
destination machine.
