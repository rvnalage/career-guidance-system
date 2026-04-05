param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 5173
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendPath = Join-Path $repoRoot "frontend"

if (-not (Test-Path $frontendPath)) {
    Write-Error "Frontend folder not found at: $frontendPath"
}

Push-Location $frontendPath
try {
    Write-Host "Starting frontend from: $frontendPath"
    Write-Host "Host: $HostName  Port: $Port"
    Write-Host "Open: http://localhost:$Port/"
    Write-Host "Press Ctrl+C (or Ctrl+Break on Windows) to stop."

    # Keep port stable: fail if busy instead of silently switching to another port.
    npm run dev -- --host=$HostName --port=$Port --strictPort
}
finally {
    Pop-Location
}
