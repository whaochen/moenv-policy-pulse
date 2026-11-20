param(
    [switch]$Force,
    [string]$CatchUpAfter = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $env:LOCALAPPDATA "MOENV-News\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$today = Get-Date -Format "yyyy-MM-dd"
$logPath = Join-Path $logDir "daily-update-$today.log"

function Write-Log {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Encoding UTF8 -Path $logPath -Value $line
}

function Test-ReportIsToday {
    $latestJson = Join-Path $repoRoot "資料\daily_update_reports\latest.json"
    if (-not (Test-Path $latestJson)) {
        return $false
    }
    try {
        $payload = Get-Content -Encoding UTF8 -Raw $latestJson | ConvertFrom-Json
        if (-not $payload.generated_at) {
            return $false
        }
        $generated = [datetimeoffset]::Parse($payload.generated_at).LocalDateTime
        return $generated.ToString("yyyy-MM-dd") -eq $today
    }
    catch {
        return $false
    }
}

if ($CatchUpAfter) {
    $target = [datetime]::ParseExact("$today $CatchUpAfter", "yyyy-MM-dd HH:mm", $null)
    if ((Get-Date) -lt $target) {
        Write-Log "Catch-up skipped before $CatchUpAfter."
        exit 0
    }
}

if (-not $Force -and (Test-ReportIsToday)) {
    Write-Log "Daily report already exists for today; skipped."
    exit 0
}

Write-Log "Starting MOENV daily update."
$updateCmd = Join-Path $repoRoot "update-index.cmd"
& $updateCmd --vault $repoRoot --daily-report --progress-every 5 *>> $logPath
$exitCode = $LASTEXITCODE
Write-Log "Update finished with exit code $exitCode."
exit $exitCode
