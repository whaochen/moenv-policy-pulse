$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

& (Join-Path $repoRoot "scripts\run_daily_update.ps1") -CatchUpAfter "09:00"
& (Join-Path $repoRoot "scripts\run_daily_email.ps1") -CatchUpAfter "09:30"
