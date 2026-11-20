$ErrorActionPreference = "Stop"

foreach ($taskName in @(
    "MOENV News Update 0900",
    "MOENV News Update Catch-up",
    "MOENV News Email 0930",
    "MOENV News Email Catch-up"
)) {
    & schtasks.exe /Delete /TN $taskName /F 2>$null
}

$startupDir = [Environment]::GetFolderPath("Startup")
$startupCmd = Join-Path $startupDir "MOENV News Catch-up.cmd"
if (Test-Path -LiteralPath $startupCmd) {
    Remove-Item -LiteralPath $startupCmd -Force
}
$startupShortcut = Join-Path $startupDir "MOENV News Catch-up.lnk"
if (Test-Path -LiteralPath $startupShortcut) {
    Remove-Item -LiteralPath $startupShortcut -Force
}

Write-Host "Removed MOENV Windows scheduled tasks."
