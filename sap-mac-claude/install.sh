#!/usr/bin/env bash
# ============================================================================
# sap-mac-claude — Claude Code configuration importer
# ----------------------------------------------------------------------------
# Copies this bundle's config into a Claude Code home ($CLAUDE_HOME, default
# ~/.claude) on a NEW machine. Idempotent and non-destructive: it backs up
# anything it would overwrite and NEVER clobbers a live settings.json (which
# holds inline API tokens).
#
# Usage:
#   ./install.sh                 # dry-run: show what WOULD happen
#   ./install.sh --apply         # actually copy files
#   CLAUDE_HOME=/path ./install.sh --apply   # target a non-default home
#
# After running, you MUST manually fill secrets — see the printed checklist
# and the README.
# ============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/config"
DST="${CLAUDE_HOME:-$HOME/.claude}"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

ts="$(date +%Y%m%d-%H%M%S)"
say()  { printf '%s\n' "$*"; }
hr()   { printf '%s\n' "------------------------------------------------------------"; }

say "sap-mac-claude importer"
hr
say "Source : $SRC"
say "Target : $DST"
[[ $APPLY -eq 0 ]] && say "Mode   : DRY-RUN (pass --apply to make changes)" || say "Mode   : APPLY"
hr

if [[ ! -d "$SRC" ]]; then
  say "ERROR: $SRC not found — run this script from inside sap-mac-claude/."
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
copy_file CLAUDE.md    CLAUDE.md
copy_dir  memory       memory
copy_dir  skills       skills
copy_dir  agent-hooks  agent-hooks
# plugin manifests tell Claude which marketplaces/plugins to (re)install
copy_dir  plugins      plugins

# --- secret-bearing files: install the TEMPLATE only if no live file exists ---
# settings.json carries inline API tokens (ANTHROPIC_AUTH_TOKEN, JIRA_PERSONAL_TOKEN,
# TYPESAFE_API_KEY) — so we seed the redacted template ONLY when there is no live
# settings.json to protect. settings.local.json is a permission allowlist (no
# secrets) and is seeded the same way for consistency.
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
install_secret_template "settings.json.template"        "settings.json"
install_secret_template "settings.local.json.template"  "settings.local.json"

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
1. Secrets: edit  $CLAUDE_HOME/settings.json  and replace every
   __SET_ME_ON_IMPORT__ :
     ANTHROPIC_AUTH_TOKEN   (gateway/proxy token for ANTHROPIC_BASE_URL)
     TYPESAFE_API_KEY       (TypeSafe / JEV — used by jev-* skills + jev hooks)
     JIRA_PERSONAL_TOKEN    (appears twice: top-level env AND mcpServers.jira.env)
2. Model gateway: settings.json points ANTHROPIC_BASE_URL at
   http://localhost:6655/anthropic/ (a local LiteLLM/proxy). If that proxy is
   not running on the new box, either start it or remove ANTHROPIC_BASE_URL /
   ANTHROPIC_AUTH_TOKEN to talk to Anthropic directly (then `claude` login).
3. Plugins: config/plugins/*.json lists the marketplaces and plugins this setup
   uses. Add the marketplaces and install the plugins on the new machine:
     /plugin marketplace add anthropics/claude-plugins-official
     /plugin marketplace add https://github.tools.sap/CPITAICoE/agent-asset-registry.git
     /plugin marketplace add typesafe-ai/skills
   then /plugin install each entry in installed_plugins.json. The two SAP/
   TypeSafe marketplaces need network access + auth to those hosts.
4. Hooks: settings.json references ~/.claude/agent-hooks/*.py (shipped in this
   bundle). They need python3 on PATH. Several import jevlib (also shipped).
   Claude Code will ask you to approve each hook once (allowlist is machine-local
   and intentionally NOT shipped).
5. MCP server "jira" uses `uvx mcp-atlassian` — needs `uv`/`uvx` installed and a
   valid JIRA_PERSONAL_TOKEN for https://jira.tools.sap.
6. Memory & permissions in settings.local.json contain machine-local absolute
   paths (e.g. /Users/C5418860/...). Edit them for the new machine.
7. Run `claude` and verify with /status, /plugin, and /hooks.
CHECK
