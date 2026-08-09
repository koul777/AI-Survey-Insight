$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$env:LOKY_MAX_CPU_COUNT = "8"
$env:OMP_NUM_THREADS = "1"

try {
    & python --version | Out-Null
} catch {
    Write-Host "Python was not found. Install Python 3.11 or newer, then run this file again." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Checking dependencies..."
& python -c "import fastapi, uvicorn, kiwipiepy, openpyxl, pandas, pydantic, pptx, sklearn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing required packages. The first run can take a few minutes."
    & python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Package installation failed." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

function Test-PortInUse {
    param([int]$Port)
    try {
        return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    } catch {
        return $false
    }
}

$port = 8001
while ((Test-PortInUse -Port $port) -and ($port -lt 8010)) {
    $port += 1
}

if (Test-PortInUse -Port $port) {
    Write-Host "Ports 8001-8010 are already in use. Stop an existing server and try again." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$url = "http://127.0.0.1:${port}"
$storagePath = if ($env:SURVEY_INSIGHT_DB_PATH) {
    $env:SURVEY_INSIGHT_DB_PATH
} else {
    Join-Path -Path $PSScriptRoot -ChildPath "out\app.db"
}
Write-Host "Starting AI Survey Insight: $url"
Write-Host "Local data storage: $storagePath"
Write-Host "Uploaded source data and analysis results may be stored there. Use the UI delete controls when no longer needed."
Write-Host "Press Ctrl+C in this window to stop the server."

Start-Process $url
& python -m uvicorn survey_insight.api:app --host 127.0.0.1 --port $port
