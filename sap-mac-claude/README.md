# sap-mac-claude

A **self-contained, importable export of a complete Claude Code configuration**,
captured from a macOS workstation. Drop this folder onto a new machine, run the
importer, fill in the secrets, and you have the same Claude Code setup: model
gateway, behavioral guidelines, memory, skills, agent-hooks, plugins, and MCP
wiring.

This folder is independent of the sibling `*-harness` folders in this repo (which
export **Hermes Agent**, a different tool). This folder exports **Claude Code**
and owns only `sap-mac-claude/`, copying nothing from outside it.

> **Secrets are redacted.** No live API keys or auth tokens are stored here.
> Every stripped value is replaced with `__SET_ME_ON_IMPORT__` and must be
> filled in manually after import (see [Secrets](#secrets-must-be-filled-in-manually)).

---

## Layout

```
sap-mac-claude/
├── README.md            ← you are here
├── MANIFEST.md          ← file inventory + counts
├── install.sh           ← idempotent importer (dry-run by default)
├── .gitignore           ← prevents live settings.json / settings.local.json from being committed
└── config/              ← the actual Claude Code config (copied into $CLAUDE_HOME)
    ├── CLAUDE.md                     global behavioral guidelines
    ├── settings.json.template        REDACTED main settings (3 secrets stripped)
    ├── settings.local.json.template  project permission allowlist (no secrets)
    ├── memory/                       memory index + long-term notes
    ├── agent-hooks/                  7 Claude-Code hooks + jevlib
    ├── skills/                       skill catalog (60 skills, 11 categories)
    └── plugins/                      marketplace + installed-plugin manifests
```

What is **deliberately NOT included** (machine-local, regenerated, or sensitive):
session history, caches, logs, daemon/runtime state, file-history, shell
snapshots, backups, and the cloned plugin marketplace contents (re-fetched on
import). See [MANIFEST.md](./MANIFEST.md) for the full list.

---

## Quick start (import onto a new machine)

Prerequisite: Claude Code is installed and has been run once (so `$CLAUDE_HOME`,
default `~/.claude`, exists).

```bash
cd sap-mac-claude

# 1. Preview exactly what will be copied (changes nothing):
./install.sh

# 2. Apply the import:
./install.sh --apply

# ...or target a non-default Claude home:
CLAUDE_HOME=/custom/.claude ./install.sh --apply
```

The importer is **non-destructive**:
- plain config files that already exist are backed up to `*.bak-<timestamp>`
  before being overwritten;
- a live `settings.json` / `settings.local.json` on the target is **never**
  touched — if absent, the redacted template is seeded there for you to fill in.

Then follow the printed checklist (and the sections below).

---

## Secrets (must be filled in manually)

Nothing secret is stored in this repo. After import, edit
`$CLAUDE_HOME/settings.json` and replace every `__SET_ME_ON_IMPORT__`:

| Location in settings.json | Variable | Purpose |
|---|---|---|
| `env` | `ANTHROPIC_AUTH_TOKEN` | token for the gateway at `ANTHROPIC_BASE_URL` |
| `env` | `TYPESAFE_API_KEY` | TypeSafe / JEV (used by jev-* skills and jev hooks) |
| `env` | `JIRA_PERSONAL_TOKEN` | SAP Jira personal access token |
| `mcpServers.jira.env` | `JIRA_PERSONAL_TOKEN` | same token, consumed by the Jira MCP server |

`settings.local.json` is a permission allowlist only — no secrets.

---

## Machine-local assumptions (this config was captured on macOS)

The config references services and paths specific to the source machine. On a
new box, make sure these exist or adjust them:

1. **Model gateway — `http://localhost:6655/anthropic/`**
   `ANTHROPIC_BASE_URL` points Claude Code at a local LiteLLM/proxy, with
   `ANTHROPIC_MODEL=claude-sonnet-4-6` and the Opus/Sonnet/Haiku defaults mapped
   to `claude-opus-4-8` / `claude-sonnet-4-6` / `claude-haiku-4-5`. If no proxy
   runs on `:6655`, either start it, or remove `ANTHROPIC_BASE_URL` +
   `ANTHROPIC_AUTH_TOKEN` to talk to Anthropic directly and log in with `claude`.
   OTEL telemetry endpoints also point at `:6655` — harmless if the proxy is
   absent (telemetry just won't export).

2. **Agent-hooks** are referenced in `settings.json` as `~/.claude/agent-hooks/*.py`.
   The hooks are **shipped in this bundle** (originally they lived under the
   Hermes home; paths were rewritten so this export is self-contained). They need
   `python3` on PATH; several import the bundled `jevlib`. Claude Code will ask
   you to approve each hook once — the allowlist is machine-local and NOT shipped.

3. **MCP server `jira`** runs `uvx mcp-atlassian` against `https://jira.tools.sap`.
   Needs `uv`/`uvx` installed and a valid `JIRA_PERSONAL_TOKEN`.

4. **`settings.local.json`** and `memory/reference_local_repos.md` contain
   machine-local absolute paths (`/Users/C5418860/...`). Edit them for the new
   machine.

---

## Plugins

`config/plugins/` records the marketplaces and plugins this setup uses. Plugin
*contents* are not shipped (they are re-fetched); add the marketplaces and
install the plugins on the target:

```
/plugin marketplace add anthropics/claude-plugins-official
/plugin marketplace add https://github.tools.sap/CPITAICoE/agent-asset-registry.git
/plugin marketplace add typesafe-ai/skills
```

then `/plugin install` each entry listed in
`config/plugins/installed_plugins.json`:

- `superpowers@claude-plugins-official`
- `code-review@claude-plugins-official`
- `skill-creator@claude-plugins-official`
- `pr-review-toolkit@claude-plugins-official`
- `chrome-devtools-mcp@claude-plugins-official`
- `aifgp-plugin-cpit-ai-coe-global-marketplace@agent-asset-registry`
- `typesafe@typesafe-ai`

The two SAP/TypeSafe marketplaces need network access and auth to those hosts.

---

## Maintaining this export (re-export after you change your live config)

To refresh this folder from the current live `~/.claude`, from inside
`sap-mac-claude/`:

```bash
SRC="${CLAUDE_HOME:-$HOME/.claude}"

# plain config
cp "$SRC/CLAUDE.md" config/CLAUDE.md
rsync -a --exclude='.DS_Store' "$SRC/memory/" config/memory/
rsync -a --exclude='__pycache__/' --exclude='*.pyc' --exclude='.DS_Store' \
  --exclude='.usage.json' --exclude='.usage.json.lock' "$SRC/skills/" config/skills/

# agent-hooks: copy the 7 CC hooks + jevlib (they live in the Hermes home)
HK="$HOME/.hermes/agent-hooks"
for h in hook_delegate_route hook_batch_guard_cc hook_bulk_io_guard \
         hook_citation_guard hook_jira_classify_cc hook_caveman_report_cc \
         hook_skill_route_cc; do cp "$HK/$h.py" config/agent-hooks/; done
rsync -a --exclude='__pycache__/' --exclude='*.pyc' "$HK/jevlib/" config/agent-hooks/jevlib/
```

Then **re-redact** `settings.json` into `config/settings.json.template`: strip
the 3 secret values above (replace with `__SET_ME_ON_IMPORT__`) and rewrite hook
command paths from `~/.hermes/agent-hooks/` to `~/.claude/agent-hooks/`. Strip
machine-local `installPath`/timestamps from the plugin manifests. Never commit a
live `settings.json`. The `.gitignore` blocks it as a safety net; always
re-check before committing:

```bash
grep -rnE '3ee73eb9|NTQ4ODMx|apikey_' config/   # must find nothing
grep -c '__SET_ME_ON_IMPORT__' config/settings.json.template
git -C .. status
```

---

## Honesty note

The import flow was validated from the source machine: the importer was dry-run
and `--apply`-tested into a scratch Claude home — all config copied, the seeded
`settings.json` parses as JSON, secrets land as `__SET_ME_ON_IMPORT__`
placeholders, and a re-run is idempotent and non-destructive (live settings
preserved, plain files backed up). Target-side steps — proxy on `:6655`, plugin
marketplace add/install, hook re-approval, `uvx` for the Jira MCP, and Anthropic
login if you drop the gateway — are **guided, not executed here**, and must be
completed on the destination machine.
