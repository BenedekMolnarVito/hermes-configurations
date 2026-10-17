# home-win-hermes

A **self-contained, importable export of a complete Hermes Agent configuration**
captured from a **Windows 11** workstation. Drop this folder onto a new machine,
run the importer, fill in the secrets, and you have the same Hermes configuration:
model routing, persona, memory, skills, agent-hooks, and (empty) cron.

> **This is the personal Windows config — intentionally separate from
> [`sap-mac-hermes`](../sap-mac-hermes)**, the macOS export. The two live in
> their own top-level folders, ship **different secret sets** and **different
> provider auth**, and must be imported into **separate** `$HERMES_HOME`
> profiles. See [CONTRIBUTING.md](../CONTRIBUTING.md) → "Config isolation".

> **Secrets are redacted.** No live API keys or auth tokens are stored here.
> Every stripped value is replaced with `__SET_ME_ON_IMPORT__` and must be
> filled in manually after import (see [Secrets](#secrets)).

---

## Layout

```
home-win-hermes/
├── README.md            ← you are here
├── MANIFEST.md          ← file inventory + counts
├── install.sh           ← idempotent importer (dry-run by default)
├── .gitignore           ← prevents live .env / auth.json from being committed
└── config/              ← the actual Hermes config (copied into $HERMES_HOME)
    ├── config.yaml              main configuration
    ├── SOUL.md                  global agent persona / standing instructions
    ├── .env.template            REDACTED env vars (settings kept, secrets stripped)
    ├── auth.json.template       REDACTED provider auth (structure only; sha256 fingerprints only)
    ├── memories/
    │   ├── MEMORY.md            agent long-term notes
    │   └── USER.md              user profile
    ├── cron/
    │   └── jobs.json            cron job DEFINITIONS (none on this personal config)
    ├── agent-hooks/             7 shell hooks + jevlib + jev-guard.json
    └── skills/                  skill catalog incl .archive (curator machinery pruned)
```

What is **deliberately NOT included** (machine-local, regenerated, or sensitive):
session history (`state.db`), caches, logs, browser profiles, runtime state
(`gateway_state.json`, pids, locks), the `hermes-agent` codebase itself,
`.env`, `auth.json`, and the skills curator machinery
(`.curator_*`, `.hub`, `.locks`, `.bundled_manifest`, per-skill `.usage.json`).

---

## Quick start (import onto a new machine)

Prerequisite: Hermes Agent is installed and has been run once (so
`$HERMES_HOME` exists). On Windows the live home is
`%USERPROFILE%\AppData\Local\hermes` (i.e. `$LOCALAPPDATA\hermes`, **not**
`~/.hermes`).

```bash
cd home-win-hermes

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
| `OPENROUTER_API_KEY` | OpenRouter model access (default + all tiers + delegation) |
| `OPENCODE_ZEN_API_KEY` | OpenCode Zen provider (if used) |
| `GITHUB_TOKEN` | GitHub API (skill search/install, gh CLI) |
| `HERMES_CUSTOM_LOCALHOST_6655_API_KEY` | local LiteLLM proxy key (unused by default here — cloud openrouter is) |
| `HINDSIGHT_API_KEY` | Hindsight long-term memory backend |
| `CUSTOM_API_KEY` | dummy key for any local Ollama-style provider (any non-empty value) |
| `TYPESAFE_API_KEY` | TypeSafe / JEV (jev-* skills + jev-guard hooks) |
| `SLACK_BOT_TOKEN` | Slack bot (Socket Mode) |
| `SLACK_APP_TOKEN` | Slack app-level token |
| `TELEGRAM_BOT_TOKEN` | Telegram bot |

All other `.env` entries are non-secret settings kept at their real values.
(The large commented block is the stock Hermes `.env` reference — harmless.)

### `$HERMES_HOME/auth.json`
Structure only — there are **no live tokens** in this file at all, only
non-reversible `sha256:` fingerprints plus provider metadata. Do **not** hand-
edit tokens in; instead run `hermes` and re-authenticate each provider. OAuth
tokens do not transfer between machines. (See `auth.json.template`.)

---

## Machine-local assumptions (this config was captured on Windows 11)

The config references services and paths specific to the source machine. On a
new box, make sure these exist or adjust them:

1. **`$HERMES_HOME` location.** On the source machine the live home is
   `%USERPROFILE%\AppData\Local\hermes` (= `$LOCALAPPDATA\hermes`), **not**
   `~/.hermes`. The importer defaults to `$LOCALAPPDATA\hermes`; override with
   `HERMES_HOME` if your install lives elsewhere.

2. **Default provider is OpenRouter (cloud).** `config.yaml` uses
   `provider: openrouter` / `base_url: https://openrouter.ai/api/v1` for the
   default model and **all** model tiers (default = `xiaomi/mimo-v2.6-pro`,
   `deep` = `meta/muse-spark-1.3-contributor`, `quick` = `z-ai/glm-5.3-flash`,
   `moderate` = `qwen/qwen3.8-flash`; delegation uses `qwen/qwen3.8-flash`).
   The `tier-router` plugin routes delegated subagents. There is **no** localhost
   LiteLLM or Ollama dependency here (unlike the mac harness) — just set
   `OPENROUTER_API_KEY`.

3. **`skills.trusted_project_dirs`** points at a Windows path:
   `C:\Users\molna\VSCodeRepos\treasury-scribe`. Edit or clear it in
   `config.yaml` for the new machine (forward-slash paths like
   `C:/Users/<you>/...` are accepted).

4. **Agent-hooks** are referenced in `config.yaml` as `~/.hermes/agent-hooks/
   *.py`. Hermes expands `~` to the home on every OS. If your `$HERMES_HOME`
   differs from the `~`-resolved path, align them or adjust the hook paths in
   `config.yaml`. On Windows Hermes auto-prepends the Python interpreter for a
   bare `.py` hook **provided Python is on PATH** — a hook erroring "cannot be
   run directly on Windows" means Python isn't on PATH, not that the hook is
   broken. The shell-hooks **allowlist is machine-local and is NOT shipped**:
   Hermes will ask you to re-approve each hook once.

5. **`memory.provider: hindsight`** needs the `hindsight` plugin installed on
   the target, its env vars present in `.env` (`HINDSIGHT_API_URL`,
   `HINDSIGHT_API_KEY`, `HINDSIGHT_BANK_ID`), and the backend reachable.
   `HINDSIGHT_BANK_ID=sap-mac-hermes` is a non-secret bank **name** carried from
   the macOS profile — rename it in `.env` if you want a fresh personal bank.

6. **No MCP servers** are configured (`mcp_servers` is empty). The dead SAP/Jira
   hook matcher that targeted SAP's internal Jira MCP was removed on export;
   `hook_jira_classify.py` remains in `agent-hooks/` (unwired) and can be
   re-pointed at any Jira MCP.

7. **Stale provider entries.** `auth.json` still lists a few credential_pool
   entries left over from the macOS port (e.g. `custom:local-(localhost:6655)`,
   `copilot`, `custom:local-litellm`). They carry sha256 fingerprints only and
   are inert; prune with `hermes auth remove` if you want them gone.

---

## Plugins

`config.yaml` enables these plugins — install them on the target before relying
on the config:

- `hindsight`
- `tier-router`

(`probe-effort-observer` is listed as disabled.) After installing, run
`hermes doctor` to confirm config, providers, and plugins are green.

---

## Cron

This personal config ships **no cron jobs**. The source profile's only cron job
("PR 259 re-review watcher") was SAP/FAA-specific (it polled `github.tools.sap`)
and was **non-functional on this Windows machine** (its backing script,
`watch_faa_pr259.sh`, was never ported). It was therefore excluded from
`cron/jobs.json`. Add your own jobs with `hermes cron` if you need them.

---

## Maintaining this export (re-export after you change your live config)

To refresh this folder from the current live `$HERMES_HOME`, re-run the same
curation the export used. From inside `home-win-hermes/` (Git Bash):

```bash
SRC="${HERMES_HOME:-$LOCALAPPDATA/hermes}"

# plain config
cp "$SRC/config.yaml"            config/config.yaml
cp "$SRC/SOUL.md"               config/SOUL.md
cp "$SRC/memories/MEMORY.md"    config/memories/
cp "$SRC/memories/USER.md"      config/memories/
cp "$SRC/cron/jobs.json"        config/cron/

# agent-hooks (prune pycache/tests/_probes)
find "$SRC/agent-hooks" -type d \( -name __pycache__ -o -name tests -o -name _probes \) -prune -o -type f -print \
  | while read -r f; do
      rel="${f#$SRC/agent-hooks/}"; mkdir -p "config/agent-hooks/$(dirname "$rel")"; cp -p "$f" "config/agent-hooks/$rel"
    done

# skills (prune curator machinery, keep .archive)
for ex in .curator_backups .curator_ledger.jsonl .curator_state .bundled_manifest .locks .hub .usage.json .usage.json.lock .DS_Store __pycache__; do
  find "$SRC/skills" -name "$ex" -prune -o -type f -print
done | while read -r f; do
    rel="${f#$SRC/skills/}"; mkdir -p "config/skills/$(dirname "$rel")"; cp -p "$f" "config/skills/$rel"
  done
```

Then **re-redact secrets** — never copy the live `.env` / `auth.json` in:
regenerate `config/.env.template` (strip the 10 secret values above, keep
settings) and `config/auth.json.template` (structure + sha256 fingerprints only).
The `.gitignore` blocks a live `.env` / `auth.json` from being committed as a
safety net, but always re-check with:

```bash
git -C .. status
grep -rn '__SET_ME_ON_IMPORT__' config/.env.template config/auth.json.template
```

before committing, and run a token-prefix scan (`ghp_`, `xoxb-`, `hsk_`,
`apikey_`, plus your own machine-key prefixes — never a real one in docs, …)
over the bundle to confirm no live secret value leaked.

---

## Honesty note

The import flow is validated as far as it can be from the source machine: the
importer supports dry-run + `--apply` into a scratch `$HERMES_HOME`,
`config.yaml` parses, secrets are seeded as `__SET_ME_ON_IMPORT__`
placeholders, and re-runs are idempotent/non-destructive. Target-side steps —
plugin install, hook re-approval, provider re-auth, and whether the OpenRouter
key is set — are **guided, not executed here**, and must be completed on the
destination machine.
