#!/usr/bin/env bash
# ============================================================================
# home-win-hermes — Hermes Agent configuration importer (Windows 11 / Git Bash)
# ----------------------------------------------------------------------------
# Copies this bundle's config into a Hermes home on a new machine. Idempotent
# and non-destructive: existing files are backed up to *.bak-<timestamp>
# before overwrite; a live .env / auth.json is NEVER overwritten — if absent,
# the redacted template is seeded for you to fill in.
#
# This config is the PERSONAL Windows-11 Hermes configuration — intentionally separate from
# the sap-mac-hermes macOS config. Do NOT import it into the same $HERMES_HOME
# that holds another config (different secret sets / provider auth / memory
# bank). See CONTRIBUTING.md "Config isolation" and the README. Use a separate
# $HERMES_HOME (or `hermes profiles`) per config.
#
# Usage (from Git Bash):
#   ./install.sh                 # dry-run: show what WOULD happen
#   ./install.sh --apply         # actually copy files
#   HERMES_HOME=/path ./install.sh --apply   # target a non-default home
#
# Source machine: Windows 11, HERMES_HOME = %USERPROFILE%\AppData\Local\hermes
# ============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/config"
DST="${HERMES_HOME:-${LOCALAPPDATA:-$HOME}/hermes}"
APPLY=0
if [[ "${1:-}" == "--apply" ]]; then APPLY=1; fi

ts="$(date +%Y%m%d-%H%M%S)"
say()  { printf '%s\n' "$*"; }
hr()   { printf '%s\n' "------------------------------------------------------------"; }

say "home-win-hermes importer"
hr
say "Source : $SRC"
say "Target : $DST"
if [[ $APPLY -eq 0 ]]; then say "Mode   : DRY-RUN (pass --apply to make changes)"; else say "Mode   : APPLY"; fi
hr

if [[ "$SRC" == "$DST" ]]; then
  say "ERROR: source and target resolve to the same path — refusing to clobber."
  exit 1
fi
if [[ ! -d "$SRC" ]]; then say "ERROR: $SRC not found — run this script from inside home-win-hermes/."; exit 1; fi
mkdir -p "$DST"

# copy_dir SUB  — mirror a directory, backing up existing target files first
copy_dir() {
  local s="$SRC/$1" d="$DST/$2"
  if [[ ! -d "$s" ]]; then say "skip (absent): $1"; return 0; fi
  if [[ -e "$d" ]]; then
    say "merge dir : $2  (existing files backed up to *.bak-$ts before overwrite)"
  else
    say "copy dir  : $2"
  fi
  if [[ $APPLY -eq 1 ]]; then
    mkdir -p "$d"
    (cd "$s" && find . -type f) | while read -r f; do
      if [[ -e "$d/$f" ]]; then cp -p "$d/$f" "$d/$f.bak-$ts"; fi
      mkdir -p "$d/$(dirname "$f")"
      cp -p "$s/$f" "$d/$f"
    done
  fi
  return 0
}

# copy_file SRC DST — never overwrite without a .bak
copy_file() {
  local s="$SRC/$1" d="$DST/$2"
  if [[ ! -f "$s" ]]; then say "skip (absent): $1"; return 0; fi
  if [[ -e "$d" ]]; then
    say "backup+copy: $2  (existing -> $2.bak-$ts)"
    if [[ $APPLY -eq 1 ]]; then cp -p "$d" "$d.bak-$ts"; cp -p "$s" "$d"; fi
  else
    say "copy file : $2"
    if [[ $APPLY -eq 1 ]]; then mkdir -p "$(dirname "$d")"; cp -p "$s" "$d"; fi
  fi
  return 0
}

# --- plain config (safe to copy) ---
copy_file config.yaml   config.yaml
copy_file SOUL.md       SOUL.md
copy_dir  memories      memories
copy_dir  cron          cron
copy_dir  agent-hooks   agent-hooks
copy_dir  skills        skills

# --- secret-bearing files: seed the TEMPLATE only if no live file exists ---
install_secret_template() {
  local tmpl="$SRC/$1" live="$DST/$2"
  if [[ ! -f "$tmpl" ]]; then return 0; fi
  if [[ -e "$live" ]]; then
    say "KEEP live  : $2 already exists — NOT touching it (fill secrets there)."
  else
    say "seed       : $2  (copied from template; EDIT & replace __SET_ME_ON_IMPORT__)"
    if [[ $APPLY -eq 1 ]]; then cp -p "$tmpl" "$live"; fi
  fi
  return 0
}
install_secret_template .env.template       .env
install_secret_template auth.json.template  auth.json

hr
if [[ $APPLY -eq 0 ]]; then
  say "DRY-RUN complete. Re-run with --apply to perform the copy."
else
  say "APPLY complete."
fi
hr
cat <<'CHECK'
MANUAL STEPS REQUIRED AFTER IMPORT
----------------------------------
1. Secrets: edit  $HERMES_HOME/.env  and replace every __SET_ME_ON_IMPORT__ :
     OPENROUTER_API_KEY, OPENCODE_ZEN_API_KEY, GITHUB_TOKEN,
     HERMES_CUSTOM_LOCALHOST_6655_API_KEY, HINDSIGHT_API_KEY, CUSTOM_API_KEY,
     TYPESAFE_API_KEY, SLACK_BOT_TOKEN, SLACK_APP_TOKEN, TELEGRAM_BOT_TOKEN
   (All other .env entries are non-secret settings kept at their real values.)
2. Provider auth: auth.json.template is structure-only (sha256 fingerprints
   only, no live tokens). Run `hermes` and re-authenticate providers — OAuth
   tokens do NOT transfer. auth.json carries a few stale provider entries from
   the macOS port (localhost:6655 / copilot / local-litellm); prune unused
   ones with `hermes auth remove` or leave them (fingerprints are non-reversible).
3. No local services required: config.yaml uses provider=openrouter (cloud)
   directly — there is NO localhost LiteLLM/Ollama dependency in this config
   (unlike the mac harness). Want local models? add them under model.aliases.
4. Plugins (config enables these): hindsight, tier-router. Install them, then
   run `hermes doctor`.
5. skills.trusted_project_dirs points at  C:\Users\molna\VSCodeRepos\treasury-scribe
   — edit or clear it in config.yaml for your machine (forward-slash paths like
   C:/Users/<you>/... are accepted).
6. Shell hooks: Hermes will ask you to re-approve each hook once (the allowlist
   is machine-local and NOT shipped). config.yaml references
   ~/.hermes/agent-hooks/*.py (Hermes expands ~ to the home); if your
   $HERMES_HOME differs from the ~-resolved path, align them or adjust the
   hook paths in config.yaml.
7. Memory bank: HINDSIGHT_BANK_ID=sap-mac-hermes is a non-secret bank NAME
   (carried from the macOS profile, not a key). It's safe in .env. Rename it
   (e.g. personal-win-hermes) if you want a fresh personal memory bank.
8. No MCP servers are configured (mcp_servers is empty). The SAP/Jira hook
   matcher targeting SAP's internal Jira MCP was removed on export (it was
   dead — that MCP is not configured here); hook_jira_classify.py is retained
   in agent-hooks/ and can be re-pointed at any Jira MCP.
9. Cron: this config ships NO cron jobs (the source profile's SAP/FAA PR-259
   watcher was excluded — it was non-functional here and SAP-specific). Add
   your own jobs with `hermes cron` if needed.
10. Run `hermes doctor` to confirm config, providers, and plugins are green.
CHECK
