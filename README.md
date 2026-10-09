# hermes-configurations

A registry of **Hermes Agent harness configurations** — one self-contained folder
per config. Each folder is an importable, redacted export of a full Hermes install
(config, persona, memory, skills, agent-hooks, cron, MCP wiring) that can be dropped
onto a new machine and brought up with its own importer.

Folders are **independent**: a config folder copies nothing from outside itself and
touching one never affects another.

## Configurations in this repo

| Folder | Source OS | Notes |
|---|---|---|
| [`sap-mac-harness/`](./sap-mac-harness) | macOS | SAP/FAA workstation; localhost LiteLLM + Ollama, hindsight memory, superpowers, jev hooks |

> Add a row here when you add a new config folder.

## Adding another configuration (e.g. a different OS or machine)

Each new config lives in its **own top-level folder** named `<org>-<os>-<purpose>`
(e.g. `sap-win-harness`, `home-linux-harness`). The full, repeatable procedure —
including the secret-redaction and cross-OS portability rules every folder in this
repo must follow — is in **[CONTRIBUTING.md](./CONTRIBUTING.md)**.

In short:
1. Create a new sibling folder; never add files to an existing config's folder.
2. Export that machine's `$HERMES_HOME` into `<folder>/config/`, pruning
   machine-local runtime state, caches, session DB, and skills curator machinery.
3. **Redact all secrets** into `*.template` files (`__SET_ME_ON_IMPORT__`
   placeholders) — never commit a live `.env` or `auth.json`.
4. Add a per-folder `README.md`, `MANIFEST.md`, `install.sh`, and `.gitignore`
   (use `sap-mac-harness/` as the reference template).
5. Document that folder's machine-local assumptions (endpoints, paths, plugins,
   MCP auth) and, for a different OS, the cross-OS caveats in CONTRIBUTING.md.
6. Add a row to the table above.

The actual authoring of a second config is **out of scope** here — this repo is
set up so one can be added by following CONTRIBUTING.md and copying the layout.
