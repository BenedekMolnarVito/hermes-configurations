# hermes-configurations

A registry of **Hermes Agent configurations** — one self-contained folder
per config. Each folder is an importable, redacted export of a full agent install
(config, persona, memory, skills, agent-hooks, cron, MCP wiring) that can be dropped
onto a new machine and brought up with its own importer. Most folders export
**Hermes Agent**; `sap-mac-claude/` and `home-win-claude/` export **Claude Code** (same export/import
discipline, different tool and home directory).

Folders are **independent**: a config folder copies nothing from a sibling and
touching one never affects another. They must be imported into **separate**
`$HERMES_HOME` locations (or separate Hermes profiles) — never merged (see
[CONTRIBUTING.md](./CONTRIBUTING.md) → "Config isolation").

## Configurations in this repo

| Folder | Source OS | Notes |
|---|---|---|
| [`sap-mac-hermes/`](./sap-mac-hermes) | macOS | SAP/FAA workstation; localhost LiteLLM + Ollama, hindsight memory, superpowers, jev hooks |
| [`home-win-hermes/`](./home-win-hermes) | Windows 11 | Personal config; cloud OpenRouter (tier-router), hindsight memory, jev hooks; no local services. Separate from sap-mac-hermes (see "Config isolation"). |
| [`home-win-claude/`](./home-win-claude) | Windows 11 | **Claude Code**, Pro subscription; tiered subagents + `orchestrate`, `.agent/` persistence + resumer, caveman inter-agent I/O, JEV (TypeSafe) routing/skills, chunked PR review. `install.ps1` / `export.ps1` round-trip. Imports into `~/.claude`. |
| [`sap-mac-claude/`](./sap-mac-claude) | macOS | **Claude Code** (not Hermes); localhost gateway on `:6655`, 7 agent-hooks + jevlib, 60 skills, superpowers/typesafe/jev plugins, Jira MCP. Imports into `~/.claude`, not `$HERMES_HOME`. |

> Add a row here when you add a new config folder.

## Adding another configuration (e.g. a different OS or machine)

Each new config lives in its **own top-level folder** named `<org>-<os>-<purpose>`
(e.g. `sap-win-hermes`, `home-linux-hermes`). The full, repeatable procedure —
including the secret-redaction and cross-OS portability rules every folder in this
repo must follow — is in **[CONTRIBUTING.md](./CONTRIBUTING.md)**.

In short:
1. Create a new sibling folder; never add files to an existing config's folder.
2. Export that machine's `$HERMES_HOME` into `<folder>/config/`, pruning
   machine-local runtime state, caches, session DB, and skills curator machinery.
3. **Redact all secrets** into `*.template` files (`__SET_ME_ON_IMPORT__`
   placeholders) — never commit a live `.env` or `auth.json`.
4. Add a per-folder `README.md`, `MANIFEST.md`, `install.sh`, and `.gitignore`
   (use `sap-mac-hermes/` or `home-win-hermes/` as the reference template).
5. Document that folder's machine-local assumptions (endpoints, paths, plugins,
   MCP auth) and, for a different OS, the cross-OS caveats in CONTRIBUTING.md.
6. Add a row to the table above.

This repo now contains four self-contained configs (`sap-mac-hermes`,
`home-win-hermes`, and the Claude Code `sap-mac-claude` and `home-win-claude`), each a complete,
independent export. See CONTRIBUTING.md to add another — configs must never be
merged into one agent home (see "Config isolation").
