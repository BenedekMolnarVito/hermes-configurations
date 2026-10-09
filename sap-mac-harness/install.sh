#!/usr/bin/env bash
# ============================================================================
# sap-mac-harness — Hermes Agent configuration importer
# ----------------------------------------------------------------------------
# Copies this bundle's config into a Hermes home ($HERMES_HOME, default
# ~/.hermes) on a NEW machine. Idempotent and non-destructive: it backs up
# anything it would overwrite and NEVER clobbers a live .env / auth.json.
#
# Usage:
#   ./install.sh                 # dry-run: show what WOULD happen
#   ./install.sh --apply         # actually copy files
#   HERMES_HOME=/path ./install.sh --apply   # target a non-default home
#
# After running, you MUST manually fill secrets — see the printed checklist
# and the README.
# ============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/config"
DST="${HERMES_HOME:-$HOME/.hermes}"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

ts="$(date +%Y%m%d-%H%M%S)"
say()  { printf '%s\n' "$*"; }
hr()   { printf '%s\n' "------------------------------------------------------------"; }

say "sap-mac-harness importer"
hr
say "Source : $SRC"
say "Target : $DST"
[[ $APPLY -eq 0 ]] && say "Mode   : DRY-RUN (pass --apply to make changes)" || say "Mode   : APPLY"
hr

if [[ ! -d "$SRC" ]]; then
  say "ERROR: $SRC not found — run this script from inside sap-mac-harness/."
  exit 1
fi
mkdir -p "$DST"

# copy_dir SRC_SUB DST_SUB  — mirror a directory, backing up existing target
copy_dir() {
  local s="$SRC/$1" d="$DST/$2"
  [[ -d "$s" ]] || { say "skip (absent): $1"; return; }
  if [[ -e "$d" ]]; then
    say "merge dir : $2  (existing files are backed up to *.bak-$ts before overwrite)"
    if [[ $APPLY -eq 1 ]]; then
      # back up each file we are about to overwrite, then rsync in
      (cd "$s" && find . -type f) | while read -r f; do
        if [[ -e "$d/$f" ]]; then cp -p "$d/$f" "$d/$f.bak-$ts"; fi
      done
      rsync -a "$s/" "$d/"
    fi
  else
    say "copy dir  : $2"
    [[ $APPLY -eq 1 ]] && { mkdir -p "$d"; rsync -a "$s/" "$d/"; }
  fi
}

# copy_file SRC_SUB DST_SUB — never overwrite without a .bak
copy_file() {
  local s="$SRC/$1" d="$DST/$2"
  [[ -f "$s" ]] || { say "skip (absent): $1"; return; }
  if [[ -e "$d" ]]; then
    say "backup+copy: $2  (existing -> $2.bak-$ts)"
    [[ $APPLY -eq 1 ]] && { cp -p "$d" "$d.bak-$ts"; cp -p "$s" "$d"; }
  else
    say "copy file : $2"
    [[ $APPLY -eq 1 ]] && { mkdir -p "$(dirname "$d")"; cp -p "$s" "$d"; }
  fi
}

# --- plain config (safe to copy) ---
copy_file config.yaml   config.yaml
copy_file SOUL.md       SOUL.md
copy_dir  memories      memories
copy_dir  cron          cron
copy_dir  agent-hooks   agent-hooks
copy_dir  skills        skills
copy_dir  scripts       scripts

# --- secret-bearing files: install the TEMPLATE only if no live file exists ---
install_secret_template() {
  local tmpl="$SRC/$1" live="$DST/$2"
  [[ -f "$tmpl" ]] || return
  if [[ -e "$live" ]]; then
    say "KEEP live  : $2 already exists — NOT touching it (fill secrets there)."
  else
    say "seed       : $2  (copied from template; EDIT IT and replace __SET_ME_ON_IMPORT__)"
    [[ $APPLY -eq 1 ]] && cp -p "$tmpl" "$live"
  fi
}
install_secret_template ".env.template"       ".env"
install_secret_template "auth.json.template"  "auth.json"

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
     OPENROUTER_API_KEY, HERMES_CUSTOM_LOCALHOST_6655_API_KEY,
     HINDSIGHT_API_KEY, CUSTOM_API_KEY, TYPESAFE_API_KEY
2. Provider auth: auth.json is structure-only. Run `hermes` and re-authenticate
   providers (OAuth tokens do NOT transfer).
3. Local services this config expects (see README "Machine-local assumptions"):
     - LiteLLM proxy on http://localhost:6655/litellm/v1  (default + all tiers)
     - Ollama on http://localhost:11434/v1               (the "Hermes MAC" provider)
   If absent on the new box, switch the default provider:  `hermes model`
4. Plugins (config enables these): delegate-pertask-model-patch, hindsight,
   hindsight-condense-patch, superpowers. Install them, then `hermes doctor`.
5. MCP sap-jira uses OAuth — it will prompt to re-auth on first use.
6. skills.trusted_project_dirs points at a mac path; edit or clear it in config.yaml.
7. Shell hooks: Hermes will ask you to re-approve each hook once (allowlist is
   machine-local and intentionally NOT shipped).
8. Run `hermes doctor` to confirm config, providers, and plugins are green.
CHECK
