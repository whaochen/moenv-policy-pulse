param(
    [switch]$Force,
    [string]$CatchUpAfter = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $env:LOCALAPPDATA "MOENV-News\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$today = Get-Date -Format "yyyy-MM-dd"
$logPath = Join-Path $logDir "daily-email-$today.log"

function Write-Log {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Encoding UTF8 -Path $logPath -Value $line
}

function Import-LocalEnv {
    $envPath = Join-Path $repoRoot "local-mail.env"
    if (-not (Test-Path $envPath)) {
        return
    }
    Get-Content -Encoding UTF8 $envPath | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $name, $value = $line.Split("=", 2)
        [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), "Process")
    }
}

if ($CatchUpAfter) {
    $target = [datetime]::ParseExact("$today $CatchUpAfter", "yyyy-MM-dd HH:mm", $null)
    if ((Get-Date) -lt $target) {
        Write-Log "Catch-up skipped before $CatchUpAfter."
        exit 0
    }
}

Import-LocalEnv

$missing = @()
foreach ($name in @("SMTP_USERNAME", "SMTP_PASSWORD", "MAIL_TO")) {
    if (-not [Environment]::GetEnvironmentVariable($name, "Process")) {
        $missing += $name
    }
}

if ($missing.Count -gt 0) {
    Write-Log ("Email skipped; missing mail settings: " + ($missing -join ", ") + ". Create local-mail.env to enable SMTP sending.")
    exit 0
}

$pythonCandidates = @()
if ($env:MOENV_PYTHON) {
    $pythonCandidates += $env:MOENV_PYTHON
}
$pythonCandidates += "C:\Users\aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $pythonCandidates += $pythonCommand.Source
}

$python = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -and (Test-Path $candidate)) {
        $python = $candidate
        break
    }
}

if (-not $python) {
    Write-Log "Email skipped; Python was not found."
    exit 0
}

$args = @((Join-Path $repoRoot "scripts\send_daily_report.py"), "--vault", $repoRoot, "--run-update-if-stale")
if ($Force) {
    $args += "--force"
}

Write-Log "Starting MOENV daily email."
& $python -B @args *>> $logPath
$exitCode = $LASTEXITCODE
Write-Log "Email finished with exit code $exitCode."
exit $exitCode
