<#
.SYNOPSIS
  home-win-claude — export the live Claude Code config back into this bundle.

.DESCRIPTION
  Reverse of install.ps1. For every file the bundle owns (everything under config/
  except settings.json.template and plugins/), copies the live version from
  $env:CLAUDE_HOME (default ~/.claude) into config/ when it differs. Then reports,
  without changing anything:
    - live files that look like new config but the bundle does not own yet
    - settings.json / plugin drift vs the template
  and scans config/ for secrets (exit 1 on a hit). Git is the backup: review `git diff`.

.EXAMPLE
  ./export.ps1          # dry-run: show what WOULD be copied + reports
  ./export.ps1 -Apply   # copy live → config/, then reports + secret scan
#>
param([switch]$Apply)
$ErrorActionPreference = 'Stop'

$Here = $PSScriptRoot
$Src  = Join-Path $Here 'config'
$Live = if ($env:CLAUDE_HOME) { $env:CLAUDE_HOME } else { Join-Path $HOME '.claude' }
function Say($m) { Write-Host $m }
function Hr { Say ('-' * 60) }

Say 'home-win-claude exporter'; Hr
Say "Live   : $Live"
Say "Bundle : $Src"
Say ("Mode   : " + ($(if ($Apply) { 'APPLY' } else { 'DRY-RUN (pass -Apply to copy)' })))
Hr

# --- 1. owned files: live → bundle (same ownership rule as install.ps1) ---
$owned = Get-ChildItem $Src -Recurse -File |
  Where-Object { $_.Name -notin 'settings.json.template', 'interruptions.log' -and
                 $_.FullName -notlike "$Src\plugins\*" -and $_.FullName -notlike '*__pycache__*' } |
  ForEach-Object { $_.FullName.Substring($Src.Length + 1) }
foreach ($rel in $owned) {
  $l = Join-Path $Live $rel; $b = Join-Path $Src $rel
  if (-not (Test-Path $l)) { Say "missing in live: $rel  (not installed? run install.ps1)"; continue }
  if ((Get-FileHash $l).Hash -eq (Get-FileHash $b).Hash) { continue }
  Say "update     : $rel"
  if ($Apply) { Copy-Item $l $b -Force }
}

# --- 2. unowned candidates (report only; copy into config/ by hand to own them) ---
# Foreign-owned, never exported: gitnexus (skills/gitnexus-*, hooks/gitnexus), RTK (RTK.md), plugin caches.
Hr; Say 'Unowned live config (add to config/ to export):'
$ownedSet = [System.Collections.Generic.HashSet[string]]::new([string[]]$owned, [StringComparer]::OrdinalIgnoreCase)
$cand = @()
foreach ($d in 'agents', 'agent-hooks', 'skills', 'bin') {
  $p = Join-Path $Live $d
  if (-not (Test-Path $p)) { continue }
  $cand += Get-ChildItem $p -Recurse -File | ForEach-Object { $_.FullName.Substring($Live.Length + 1) } |
    Where-Object { $_ -notmatch '\.bak-\d|__pycache__|interruptions\.log$|^skills\\(gitnexus-|synced\\)' -and
                   -not $ownedSet.Contains($_) }
}
if ($cand) { $cand | ForEach-Object { Say "  candidate: $_" } } else { Say '  none' }

# --- 3. settings + plugin drift (report only; edit settings.json.template / plugins.json by hand) ---
Hr
& python (Join-Path $Here 'settings_drift.py') (Join-Path $Src 'settings.json.template') (Join-Path $Live 'settings.json') $Live
$ip = Join-Path $Live 'plugins\installed_plugins.json'
if (Test-Path $ip) {
  $have = (Get-Content $ip -Raw | ConvertFrom-Json).plugins.PSObject.Properties.Name
  $want = (Get-Content (Join-Path $Src 'plugins\plugins.json') -Raw | ConvertFrom-Json).plugins
  $have | Where-Object { $_ -notin $want } | ForEach-Object { Say "live-only plugin install: $_  (add to plugins/plugins.json or README Optional)" }
}

# --- 4. secret scan over the bundle (live values of known secret env vars + key shapes) ---
Hr
$hits = @()
$vals = 'TYPESAFE_API_KEY', 'ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY', 'TELEGRAM_BOT_TOKEN', 'GITHUB_TOKEN' |
  ForEach-Object { [Environment]::GetEnvironmentVariable($_) } | Where-Object { $_ -and $_.Length -ge 16 }
$shape = 'sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-[A-Za-z0-9-]{20,}|\d{8,10}:[A-Za-z0-9_-]{30,}|Bearer [A-Za-z0-9._-]{20,}'
Get-ChildItem $Here -Recurse -File | Where-Object { $_.FullName -notlike '*__pycache__*' -and $_.Extension -ne '.pyc' } |
  ForEach-Object {
    $t = Get-Content $_.FullName -Raw
    if (-not $t) { return }
    foreach ($v in $vals) { if ($t.Contains($v)) { $hits += "$($_.FullName): live secret value" } }
    if ($t -cmatch $shape) { $hits += "$($_.FullName): key-shaped string '$($Matches[0].Substring(0,6))...'" }
  }
if ($hits) { $hits | ForEach-Object { Say "SECRET?    : $_" }; Hr; Say 'Secret scan FAILED — redact before committing.'; exit 1 }
Say 'secret scan: clean'
Hr
Say $(if ($Apply) { 'EXPORT complete. Review: git diff -- home-win-claude' } else { 'DRY-RUN complete. Re-run with -Apply to copy.' })
