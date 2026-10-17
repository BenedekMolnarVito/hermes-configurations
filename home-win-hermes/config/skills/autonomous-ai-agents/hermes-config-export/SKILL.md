---
name: hermes-config-export
description: "Use when exporting or refreshing a shareable config bundle."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, config, export, redaction, secrets, harness, git, leak-gate]
---

# Hermes Config Export (secret-free bundles)

Produce or refresh a shareable, secret-free Hermes config export — e.g. the
per-OS harness folders (`home-win-harness/`, `sap-mac-harness/`) in the
`hermes-configurations` repo. Governs the loop:
refresh from live `$HERMES_HOME` → redact → value-sweep → leak gate →
independent audit → commit/push. The import direction (decrypt/copy onto a
target) is `hermes-config-migration`; the two are complementary halves.

## When to Use

- Refreshing an existing harness folder after changing the live config
- Adding a new per-OS / per-machine config folder to the repo
- Any Hermes config snapshot that will be committed or published anywhere

## Ground rule

The bundle contains **zero live secret values** — always, no exceptions. The
user calls this out explicitly on every export. A single leaked value is a
blocking defect; never ship a bundle on a self-reported clean gate.

## Procedure

### 1. Take the file lists from the repo docs, not from memory
Read the target folder's `README.md` §"Maintaining this export" (exact
copy/prune recipe) and `CONTRIBUTING.md` (golden rules; redaction spec;
leak gate; config isolation). Those docs are authoritative for what to ship
and how to name things; this skill carries the workflow order and pitfalls.
Never invent a file list.

### 2. Refresh the tree from live `$HERMES_HOME`
Copy with `cp -p`: `config.yaml`, `SOUL.md`, `memories/`, `cron/jobs.json`,
`agent-hooks/` (prune `__pycache__`/`tests`/`_probes`), `skills/` (prune curator
machinery per the folder README, keep `.archive`). **Never copy live `.env` or
`auth.json` into the repo at any point.**

### 3. Re-apply the deviations policy
`MANIFEST.md` §"Deviations" is standing policy, not history: every refresh
re-applies it (de-SAP'd hook matchers, excluded machine-dead cron jobs, etc.)
or the removed content silently returns with the copy. Report what the live
source actually contains (e.g. live cron job list) instead of trusting old
notes.

### 4. Regenerate the redacted templates programmatically
- `.env.template`: keep header/comments and non-secret settings verbatim;
  every secret value → `__SET_ME_ON_IMPORT__` (key names matching
  `KEY|TOKEN|SECRET|PASS|CRED|API_KEY`, minus pure settings like
  `HERMES_MAX_TOKENS`, `*_MODEL`, `*_BASE_URL`, `*_BANK_ID`, `*_API_URL`).
- `auth.json.template`: structure + metadata + `sha256:` fingerprints kept;
  any raw token/secret string → `__SET_ME_ON_IMPORT__`.
- Redact with a script that touches values in memory only. **Never print a
  live secret value** — not in tool output, reports, commit messages, or
  chat. Reports carry key NAMES and counts only.

### 5. Value-sweep the whole bundle (what key-name redaction misses)
Run `scripts/secret_sweep.py` (see its header for usage): it reads the live
secret values and byte-searches every bundle file for them, reporting only
`OK` / `LEAKED: <file>:<line> (<key name>)`. Fix every hit, re-run to clean.

### 6. Refresh MANIFEST/README truthfully
Recompute all counts (files, total bytes, `SKILL.md` count, hook `.py` count,
cron jobs, auth providers, redacted keys, `Generated:` date) — never carry old
numbers forward. Bring README claims (model tiers, plugins, secret tables,
machine-local notes) in line with the tree.

### 7. Leak gate → independent audit → commit/push
1. Leak gate: placeholder grep, token-prefix grep
   (`ghp_|xoxb-|xapp-|hsk_|apikey_|sk-or-v1-|sk-proj-|…`), value-sweep clean,
   no untemplated `.env`/`auth.json` in the bundle, `config.yaml` parses.
2. Orchestration: the export worker leaves the tree **uncommitted**; a
   separate auditor with fresh context adversarially re-runs the gate on the
   uncommitted diff; only after PASS does the hub commit and push. Never push
   before the audit — a pushed leak needs history rewriting.

## Pitfalls

- **Key-name redaction alone leaks twice over**: commented-out duplicate
  `# KEY=<live value>` lines in `.env` dodge `^KEY=` redaction, and secret
  values get baked into doc/skill examples ("any non-empty value" dummies
  included). The byte-wise value sweep of step 5 is the only check that finds
  both — key-name matching is necessary but not sufficient.
- **A token-prefix grep is not a leak gate.** It only catches well-known
  shapes; an opaque 32-char key matches nothing. Prefix scan AND value sweep,
  never either alone.
- **A subagent's "leak_gate_clean: true" is a claim, not a gate.** Run the
  audit in a fresh context before the commit/push boundary (step 7).
- **Keep destructive pruning (`rm -rf`, `find -delete`) out of batched copy
  commands.** Approval gates deny the whole batch and the copy work is lost;
  run copies first, prune in separate minimal commands (`rmdir` where
  possible).
- **Don't re-save copied files through an editor** — `core.autocrlf=true`
  makes `git diff` line-ending-noisy but repo blobs stay LF; re-saving risks
  BOMs and real diffs. Copy bytes, edit only what the deviations require.
- **`config.yaml` is write-protected** from `write_file`/`patch` — apply
  deviation edits via terminal redirection or `hermes config edit` (see
  `hermes-config-migration` pitfalls; Notepad adds a BOM → HTTP 400).
- **Report files are not secret-free zones by default.** The export report must
  state key names, counts, and `OK`/`LEAKED` verdicts — a value "for reference"
  in a report is already a leak.
