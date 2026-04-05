param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $repoRoot "backend"

if (-not (Test-Path $backendPath)) {
    Write-Error "Backend folder not found at: $backendPath"
}

Push-Location $backendPath
try {
    Write-Host "Starting backend from: $backendPath"
    Write-Host "Host: $HostName  Port: $Port  Reload: $($NoReload.IsPresent -eq $false)"
    Write-Host "Press Ctrl+C (or Ctrl+Break on Windows) to stop."

    if ($NoReload.IsPresent) {
        & python -m uvicorn app.main:app --host $HostName --port $Port
    }
    else {
        & python -m uvicorn app.main:app --host $HostName --port $Port --reload
    }
}
finally {
    Pop-Location
}
