param(
    [string]$VaultPath = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

$ErrorActionPreference = "Stop"

$vault = (Resolve-Path -LiteralPath $VaultPath).Path
$powerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

function Install-MoenvTask {
    param(
        [string]$Name,
        [string]$Schedule,
        [string]$StartTime,
        [string]$ScriptName,
        [string]$ExtraArgs
    )

    $script = Join-Path $vault "scripts\$ScriptName"
    $taskRun = "`"$powerShell`" -NoProfile -ExecutionPolicy Bypass -File `"$script`" $ExtraArgs"
    $arguments = @(
        "/Create", "/TN", $Name,
        "/TR", $taskRun,
        "/SC", $Schedule,
        "/F",
        "/RL", "LIMITED",
        "/RU", $currentUser,
        "/IT"
    )
    if ($StartTime) {
        $arguments += @("/ST", $StartTime)
    }

    & schtasks.exe @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create scheduled task: $Name"
    }
}

Install-MoenvTask `
    -Name "MOENV News Update 0900" `
    -Schedule "DAILY" `
    -StartTime "09:00" `
    -ScriptName "run_daily_update.ps1" `
    -ExtraArgs "-Force"

Install-MoenvTask `
    -Name "MOENV News Email 0930" `
    -Schedule "DAILY" `
    -StartTime "09:30" `
    -ScriptName "run_daily_email.ps1" `
    -ExtraArgs ""

$startupDir = [Environment]::GetFolderPath("Startup")
$legacyStartupCmd = Join-Path $startupDir "MOENV News Catch-up.cmd"
if (Test-Path -LiteralPath $legacyStartupCmd) {
    Remove-Item -LiteralPath $legacyStartupCmd -Force
}
$startupShortcut = Join-Path $startupDir "MOENV News Catch-up.lnk"
$startupScript = Join-Path $vault "scripts\startup_catchup.ps1"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($startupShortcut)
$shortcut.TargetPath = $powerShell
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$startupScript`""
$shortcut.WorkingDirectory = $vault
$shortcut.Save()

Write-Host "Installed MOENV Windows scheduled tasks for vault:"
Write-Host $vault
Write-Host "Installed startup catch-up script:"
Write-Host $startupShortcut
