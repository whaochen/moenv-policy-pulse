param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$IndexerArgs
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $repoRoot "scripts\moenv_news_indexer.py"

$candidates = @()
if ($env:MOENV_PYTHON) {
    $candidates += $env:MOENV_PYTHON
}
$candidates += "C:\Users\aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $candidates += $pythonCommand.Source
}

$python = $null
foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate)) {
        $python = $candidate
        break
    }
}

if (-not $python) {
    throw "Python was not found. Install Python or set MOENV_PYTHON to python.exe."
}

$defaultArgs = @("--use-curl")
if ($IndexerArgs -contains "--use-curl") {
    $defaultArgs = @()
}

& $python -B $scriptPath @defaultArgs @IndexerArgs
exit $LASTEXITCODE
