<#
.SYNOPSIS
  home-win-claude — Claude Code configuration importer for Windows.

.DESCRIPTION
  Copies this bundle into a Claude Code home ($env:CLAUDE_HOME, default ~/.claude).
  Idempotent and non-destructive: changed files are backed up to *.bak-<timestamp>,
  settings.json is MERGED (local keys and hooks such as GitNexus are kept), never replaced.

.EXAMPLE
  ./install.ps1                    # dry-run: show what WOULD happen
  ./install.ps1 -Apply             # copy files + merge settings.json
  ./install.ps1 -Apply -Plugins    # ...and add marketplaces / install resumer + caveman
  ./install.ps1 -Apply -Rtk        # ...and install RTK output filtering (winget)
#>
param(
  [switch]$Apply,
  [switch]$Plugins,
  [switch]$Rtk
)
$ErrorActionPreference = 'Stop'

$Here = $PSScriptRoot
$Src  = Join-Path $Here 'config'
$Dst  = if ($env:CLAUDE_HOME) { $env:CLAUDE_HOME } else { Join-Path $HOME '.claude' }
$Ts   = Get-Date -Format 'yyyyMMdd-HHmmss'

function Say($m) { Write-Host $m }
function Hr { Say ('-' * 60) }

Say 'home-win-claude importer'; Hr
Say "Source : $Src"
Say "Target : $Dst"
Say ("Mode   : " + ($(if ($Apply) { 'APPLY' } else { 'DRY-RUN (pass -Apply to make changes)' })))
Hr

# --- preflight: real python (python3 is the MS Store stub on many Windows boxes) ---
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py -or $py.Source -like '*WindowsApps*') {
  throw 'A real `python` (3.9+) must be on PATH — hooks run `python ...`. Install from python.org or scoop.'
}
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { throw '`claude` not on PATH — install Claude Code first.' }

# Copy-Item with a .bak when the target exists and differs.
function Install-File([string]$rel, [string]$dstRel = $rel) {
  $s = Join-Path $Src $rel; $d = Join-Path $Dst $dstRel
  if (Test-Path $d) {
    if ((Get-FileHash $s).Hash -eq (Get-FileHash $d).Hash) { Say "same       : $dstRel"; return }
    Say "backup+copy: $dstRel  (existing -> $dstRel.bak-$Ts)"
    if ($Apply) { Copy-Item $d "$d.bak-$Ts"; Copy-Item $s $d -Force }
  } else {
    Say "copy       : $dstRel"
    if ($Apply) { New-Item -ItemType Directory -Force (Split-Path $d) | Out-Null; Copy-Item $s $d }
  }
}

# --- plain config: only the files this bundle owns (other skills/hooks are left alone) ---
Get-ChildItem $Src -Recurse -File |
  Where-Object { $_.Name -notin 'settings.json.template', 'interruptions.log' -and
                 $_.FullName -notlike "$Src\plugins\*" -and $_.FullName -notlike '*__pycache__*' } |
  ForEach-Object { Install-File $_.FullName.Substring($Src.Length + 1) }

# --- settings.json: merge, never clobber ---
$mergeArgs = @((Join-Path $Here 'merge_settings.py'), (Join-Path $Src 'settings.json.template'),
               (Join-Path $Dst 'settings.json'), $Dst)
if ($Apply) { $mergeArgs += '--apply' }
& python @mergeArgs

# --- plugins (playbook: resumer for rate-limit recovery, caveman in manual mode) ---
if ($Plugins) {
  $manifest = Get-Content (Join-Path $Src 'plugins/plugins.json') -Raw | ConvertFrom-Json
  $known = (& claude plugin marketplace list 2>$null) -join "`n"
  foreach ($m in $manifest.marketplaces.PSObject.Properties) {
    if ($known -match [regex]::Escape($m.Name)) { Say "marketplace: $($m.Name) already added"; continue }
    Say "marketplace: add $($m.Value)"
    if ($Apply) { & claude plugin marketplace add $m.Value }
  }
  foreach ($p in $manifest.plugins) {
    Say "plugin     : install $p"
    if ($Apply) { & claude plugin install $p --scope user }
  }
  # resumer ships without node_modules; its MCP channel server needs them.
  $ip = Join-Path $Dst 'plugins/installed_plugins.json'
  if ($Apply -and (Test-Path $ip)) {
    $entry = (Get-Content $ip -Raw | ConvertFrom-Json).plugins.'resumer@wong2-plugins'
    foreach ($e in @($entry)) {
      if ($e.installPath -and -not (Test-Path (Join-Path $e.installPath 'node_modules'))) {
        Say "npm install: $($e.installPath)"
        Push-Location $e.installPath; try { & npm install --omit=dev --no-audit --no-fund } finally { Pop-Location }
      }
    }
  }
}

# --- RTK output filter (playbook §4): third-party binary, manages its own hook + RTK.md ---
if ($Rtk) {
  if (-not (Get-Command rtk -ErrorAction SilentlyContinue)) {
    Say 'rtk        : winget install rtk-ai.rtk'
    if ($Apply) {
      & winget install --id rtk-ai.rtk -e --accept-source-agreements --accept-package-agreements --disable-interactivity
      $env:Path += ";$env:LOCALAPPDATA\Microsoft\WinGet\Links"
    }
  }
  Say 'rtk        : rtk init -g --auto-patch  (adds PreToolUse:Bash hook + @RTK.md)'
  if ($Apply) { & rtk init -g --auto-patch }
}

Hr
Say $(if ($Apply) { 'APPLY complete.' } else { 'DRY-RUN complete. Re-run with -Apply to perform the copy.' })
Hr
@"
AFTER IMPORT
------------
1. Restart Claude Code (CLAUDE.md, agents and plugins load at session start).
   Verify: /hooks (SessionStart, StopFailure, PreToolUse:Agent), /agents (scout,
   implementer, reviewer, synthesizer), /plugin (resumer, caveman), /context.
2. Auto-resume after a rate limit only works when launched through the resumer channel:
     pwsh -File $Dst\bin\claude-resumable.ps1 [--add-dir <repo> ...]
   Keep that window open while the limit resets. Manual fallback: claude --continue,
   then "Resume per the persistence protocol."
3. No secrets in this bundle: Pro subscription login (claude /login). Make sure
   ANTHROPIC_API_KEY is NOT set, or Claude Code bills the API instead of Pro.
4. Caveman is installed in manual mode: off until you type /caveman.
"@ | Write-Host
