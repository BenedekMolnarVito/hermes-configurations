# Contributing a new Hermes configuration

This repo holds one **self-contained, importable folder per Hermes Agent config**.
This guide is the repeatable procedure for adding another one — most often a config
captured on a **different OS or machine** than the ones already here. It also fixes
the conventions every folder must follow so configs stay portable and secret-free.

Authoring a specific new config is intentionally **out of scope** of the current
work; this document exists so it can be done cleanly later by whoever has that
machine.

---

## 1. Golden rules (apply to every folder)

1. **One folder per config, fully isolated.** Name it `<org>-<os>-<purpose>`
   (e.g. `sap-win-harness`, `home-linux-harness`, `sap-mac-harness`). A folder
   must reference and copy only files inside itself.
2. **Never commit live secrets.** No real `.env`, no real `auth.json`, no tokens
   or keys anywhere. Secrets are stripped into `*.template` files with
   `__SET_ME_ON_IMPORT__` placeholders and flagged for manual entry on import.
3. **Export essentials, not runtime state.** Exclude session history (`state.db`
   and `-wal`/`-shm`), caches, logs, browser profiles, pids/locks/gateway state,
   cron run-history (`executions.db`), the `hermes-agent` codebase, and the skills
   curator machinery.
4. **Each folder is independently importable** with its own `README.md`,
   `MANIFEST.md`, `install.sh`, and `.gitignore`. Use `sap-mac-harness/` as the
   reference template — copy its structure and adapt.
5. **Document machine-local assumptions.** Any endpoint, path, plugin, or service
   the config depends on must be spelled out in that folder's README so an
   importer knows what to stand up or change.
6. **Configs never collide.** A config folder is a complete, self-contained
   `$HERMES_HOME` export for ONE machine/profile (see §6). Never import two
   config folders into the same `$HERMES_HOME` — they carry different secret
   sets, provider auth, cron jobs, and memory banks, and the second import will
   back up then overwrite the first. To run two configs side-by-side, use
   separate `$HERMES_HOME` directories or `hermes profiles`.

---

## 2. Standard folder layout

```
<org>-<os>-<purpose>/
├── README.md            import + maintenance guide, machine-local caveats
├── MANIFEST.md          file inventory + counts
├── install.sh           idempotent, non-destructive importer (dry-run default)
├── .gitignore           blocks live .env / auth.json / secrets
└── config/              the Hermes config copied into $HERMES_HOME on import
    ├── config.yaml
    ├── SOUL.md
    ├── .env.template            redacted env (settings kept, secrets stripped)
    ├── auth.json.template       redacted provider auth (structure only)
    ├── memories/{MEMORY.md,USER.md}
    ├── cron/jobs.json           job DEFINITIONS only
    ├── agent-hooks/             hooks + any lib they import
    ├── scripts/                 scripts referenced by cron/hooks
    └── skills/                  skill catalog (curator machinery pruned)
```

---

## 3. Procedure to add a config

Run this on the machine whose config you are exporting. Resolve its Hermes home
from `$HERMES_HOME` (default `~/.hermes` on macOS/Linux,
`%USERPROFILE%\.hermes` on Windows) — never hardcode a path.

1. **Create the folder** at the repo root; add `config/`.
2. **Copy the essentials** into `config/`, pruning as in the golden rules:
   - `config.yaml`, `SOUL.md`
   - `memories/MEMORY.md`, `memories/USER.md`
   - `cron/jobs.json` (definitions only — not `executions.db`)
   - `agent-hooks/` excluding `__pycache__`, `tests/`, `_probes/`
   - `scripts/` that the cron jobs / hooks call
   - `skills/` excluding `.curator_backups/`, `.curator_ledger.jsonl`,
     `.curator_state`, `.bundled_manifest`, `.locks/`, `.hub/`, `__pycache__/`,
     `.usage.json`(+`.lock`), `.DS_Store`. Keep `.archive/`.
   (The "Maintaining this export" section of `sap-mac-harness/README.md` has the
   exact `rsync` commands — reuse them.)
3. **Redact secrets:**
   - `config/.env.template`: strip every secret VALUE (anything whose key matches
     `KEY|TOKEN|SECRET|PASS|CRED|API_KEY`, except plain settings like
     `HERMES_MAX_TOKENS`) to `__SET_ME_ON_IMPORT__`; keep non-secret settings at
     their real values; keep the comment block.
   - `config/auth.json.template`: keep structure, replace all token/secret string
     values with `__SET_ME_ON_IMPORT__` (fingerprints like `sha256:...` are
     non-reversible and may stay).
4. **Add the four support files** (`README.md`, `MANIFEST.md`, `install.sh`,
   `.gitignore`) by copying `sap-mac-harness/`'s and adapting the names, the
   secret list, and the machine-local section.
5. **Run the secret-leak gate** before committing — no full live `.env`/`auth.json`
   value may appear anywhere in the folder:
   ```bash
   grep -rn '__SET_ME_ON_IMPORT__' <folder>/config/.env.template \
                                   <folder>/config/auth.json.template
   # and diff against the live files to confirm no real value leaked
   # also scan the bundle for real token prefixes — only comment/doc examples
   # or sha256: fingerprints should appear:
   grep -rnE 'ghp_|xoxb-|xapp-|hsk_|apikey_|3ee73eb9|sk-or-v1-|sk-proj-' <folder>/config/ || true
   ```
6. **Register it:** add a row to the table in the top-level `README.md`.

---

## 4. Cross-OS caveats (when the new config targets a different OS)

These are the portability points that cost the most time; cover them in the new
folder's README:

- **Paths.** Rewrite machine-local absolute paths (e.g. `skills.trusted_project_dirs`)
  for the target. Forward-slash Windows paths (`C:/Users/<you>/...`) are accepted
  everywhere; `~` expands on every OS.
- **`localhost` providers.** `model.base_url` / `custom_providers` pointing at
  `localhost` (LiteLLM proxy, Ollama) are environment-specific: they only work if
  the same service runs on the target. Document the fallback — switch to a direct
  cloud provider with `hermes model`.
- **Config file encoding (Windows).** Never re-save `config.yaml` in Notepad — it
  writes a UTF-8 BOM and Hermes then returns HTTP 400 "No models provided". Use
  `hermes config edit` or an editor set to "UTF-8 without BOM".
- **Shell hooks.** No command rewrite needed cross-OS: Hermes auto-prepends the
  interpreter for a bare `.py`/`.sh` hook (on Windows via `sys.executable`),
  provided the interpreter is on PATH. A hook erroring "cannot be run directly on
  Windows" means Python isn't found, not that the hook is wrong. The shell-hooks
  **allowlist is machine-local — never ship it**; the user re-approves each hook
  once on the new machine.
- **Plugins.** Install the plugins the config's `plugins.enabled` lists on the
  target, then run `hermes doctor`. `memory.provider: hindsight` (or any plugin
  provider) also needs its env vars present and backend reachable.
- **OAuth MCP servers** (`auth: oauth`) re-authenticate on first use on the new
  machine; `auth.json` tokens do not transfer.

---

## 5. Honesty gate

You cannot test the actual import on the other OS from the exporting machine.
Verify what you can locally (importer dry-run + `--apply` into a scratch home,
`config.yaml` parses, placeholders present, re-run idempotent), and label the
target-side steps (plugin install, hook approval, provider switch, MCP re-auth,
localhost services) as **guided, not executed**. Do not present an un-run sequence
as validated.

---

## 6. Config isolation (configs must never collide)

Each top-level folder in this repo is a **complete, self-contained Hermes
configuration for a single machine/profile**. They are deliberately NOT
mergeable, and importing two of them into the same `$HERMES_HOME` will
overwrite one with the other:

- **Different secrets.** Each config redacts its own `.env` secret set (which
  varies per machine — e.g. `home-win-harness` redacts 10 keys vs.
  `sap-mac-harness`'s 5). Never copy a live `.env`/`auth.json` between folders.
- **Different provider auth.** `auth.json` holds per-machine provider
  credentials (sha256 fingerprints only here); OAuth tokens do not transfer.
  Importing config B over config A's live home leaves A's live `.env`/`auth.json`
  untouched (non-destructive), but `config.yaml`, skills, memories, and cron
  **will** be backed up and overwritten/merged.
- **Different memory banks.** `HINDSIGHT_BANK_ID` and the `hindsight`-memory
  plugin state are per-config; merging homes mixes memory banks.
- **Different cron.** Each config's `cron/jobs.json` defines that machine's
  jobs; importing overwrites the target's cron.
- **Different machine-local paths.** `skills.trusted_project_dirs`, hook paths,
  and service endpoints are per-machine.

**To run two configs side-by-side on one machine, use separate Hermes profiles
(`hermes profiles`) or separate `$HERMES_HOME` directories** — never drop two
configs' `config/` trees into the same home. Each folder's `README.md` and
`MANIFEST.md` state the source machine and `HERMES_HOME` so they cannot be
confused; add a row to the top-level `README.md` config table when you add a
folder.
