---
name: hermes-config-migration
description: "Use to export/import a Hermes install to another machine/OS."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, backup, export, import, migration, windows, secrets, portability]
---

# Hermes config export / import / migration

## When to Use

Trigger when the user wants to export, back up, clone, or migrate a Hermes install to another machine or OS (incl. macOS->Windows), or produce a portable/importable config bundle. Not for in-place config edits on one machine (that is hermes-agent).

Move a Hermes install (config, skills, memory, cron, secrets) to another machine or OS and get it running on the first try. Two routes: Hermes' built-in full-home backup, or a hand-built curated bundle when the user wants essentials without the (large, machine-tied) session database.

## Decide the route first (ask if unclear)

- Full 1:1 clone INCLUDING session history -> use the built-in commands, do not hand-roll:
  - source:  `hermes backup -o <file>.zip`   (full home, auto-excludes codebase/caches/runtime-local state)
  - target:  `hermes import <file>.zip`
- Essentials only (config + skills + memory + cron + secrets, NO session history) -> hand-build a curated bundle (below). `hermes backup` always snapshots the full `state.db` (often 100 MB+), so it is the wrong tool when the user explicitly wants it left out.
- Cross-OS (e.g. macOS -> Windows) -> curated bundle PLUS a Windows-ported config and a caveats guide; the raw config carries machine-local paths/services that need porting.

Always run the three decisions as ONE clarify call up front: (1) scope (full / essentials / no-secrets), (2) how to handle machine-local items (rewrite+document / as-is+list / omit), (3) transfer security (encrypt / trusted channel / no-secrets). They shape the entire output.

## What `hermes backup` actually bundles (verify, don't guess)

Confirmed from `hermes_cli/backup.py`:
- INCLUDES secrets: `.env`, `auth.json`, `state.db`, local vault (`vault.key`, `vault.json.enc`). Restored owner-only (0600). The archive itself is sensitive — treat accordingly.
- EXCLUDES: the `hermes-agent` codebase (re-clone/`hermes update`), venvs/`node_modules`/caches, `browser-profile`/`browser_profiles` credential snapshots, SQLite `-wal`/`-shm` sidecars, prior `backups/`, quick `state-snapshots/`.
- On IMPORT, machine-local runtime state is deliberately skipped: `gateway_state.json`, `gateway.pid`, `cron.pid`, `gateway.lock`, `processes.json`, PM runtime roots. This is exactly what you want cross-machine — never force these across.

## Curated bundle procedure (essentials-only / cross-OS)

1. Resolve the real home from `$HERMES_HOME` (profile-safe), never hardcode `~/.hermes`.
2. Stage a clean tree and copy only the user-scoped essentials:
   - `config.yaml` (keep the original as reference), `SOUL.md`
   - `.env`, `auth.json` (secrets)
   - `skills/` but PRUNE the curator machinery: `.curator_backups/` (large tarballs), `.curator_ledger.jsonl`, `.curator_state`, `.bundled_manifest`, `.locks/`, `.hub/`, per-skill `.usage.json`. Keep `.archive/` (restorable user skills). This typically halves the size.
   - `memories/MEMORY.md`, `memories/USER.md`
   - `cron/jobs.json` (job DEFINITIONS only — never `executions.db`, that is local run history)
   - `agent-hooks/` if the config's `hooks:` reference scripts there (plus the lib package they import), excluding `__pycache__`, `tests/`, `_probes/`.
3. Generate a MANIFEST (file list + sizes + counts) — never dump secret VALUES into it.
4. Produce a `.env.template` (var NAMES + one-line purpose, mark `(SECRET)` vs plain setting, NO values) so the guide can explain what must be set without exposing anything.
5. Write the import guide (see references/windows-import-guide-outline.md for the section skeleton).
6. Encrypt before delivery when secrets are inside (below), verify the round-trip, then SHRED the plaintext staging + tarball.

## Secret handling

- The curated `.env`/`auth.json` are REAL credentials in your staging dir. NEVER print their contents in chat; the deliverable must be encrypted or secret-free.
- Encrypt with a tool present on BOTH ends. `openssl` is near-universal (ships with Git for Windows) when `age`/`gpg`/`7z` are absent:
  `openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -in bundle.tar.gz -out bundle.tar.gz.enc -pass pass:"$PASS"`
  Decrypt: same with `-d`. Pick the iteration count the same on both sides.
- Generate a strong random passphrase; write it to a 0600 file for the user to move to their password manager, and DELIVER IT OUT OF BAND — never in chat, never inside the bundle, never over the same channel as the `.enc`.
- SHA-256 the ENCRYPTED artifact (safe to share) for integrity.
- ALWAYS verify recoverability before handing over: decrypt + extract to a temp dir, confirm the tree + `.env` present + the ported YAML still parses, then delete the temp dir.

## macOS -> Windows caveats (the ones that cost time)

- Shell HOOKS need NO command rewrite. Hermes on Windows auto-prepends the interpreter for a bare `.py`/`.sh` hook (`.py -> python` via `sys.executable`, see `agent/shell_hooks.py` `_WINDOWS_SCRIPT_INTERPRETERS`) and `os.path.expanduser` expands `~` to `%USERPROFILE%`. So `~/.hermes/agent-hooks/x.py` works unchanged — PROVIDED Python is on PATH. A hook erroring 'cannot be run directly on Windows' means Python isn't found, not that the hook is wrong.
- The shell-hooks allowlist is machine-local and must NOT be ported: it stores script mtimes that won't match after copy. Leave it out; the user re-approves each hook once in a `hermes` session.
- NEVER re-save `config.yaml` in Notepad: it writes a UTF-8 BOM and Hermes then returns HTTP 400 'No models provided'. Use `hermes config edit` or an editor set to 'UTF-8 without BOM'.
- `model.base_url`/`custom_providers` pointing at `localhost` (LiteLLM proxy, Ollama) are ENVIRONMENT-specific, not OS-specific: they only work if the same service runs on the target. Document switching to a direct cloud provider via `hermes model` as the fallback.
- Machine-local config paths (e.g. `skills.trusted_project_dirs`) must be emptied or rewritten with forward-slash Windows paths (`C:/Users/<you>/...` is accepted everywhere).
- OAuth MCP servers (`auth: oauth`) re-auth on first use on the new machine; don't assume `auth.json` tokens transfer.
- `memory.provider: hindsight` (or any plugin provider) needs its plugin installed on the target AND its env vars present AND the backend reachable.
- After import, install the plugins the config's `plugins.enabled` lists, then `hermes doctor` to confirm config/provider/plugins are green.

## Honesty gate

You cannot test the actual import on the other OS from the source machine. Verify what you CAN (decrypt/extract/parse), and label the target-side steps (plugin install, hook approval, provider switch, MCP re-auth) as guided, not executed. Do not present an un-run sequence as validated.
