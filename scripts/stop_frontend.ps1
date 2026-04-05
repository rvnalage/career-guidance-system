param(
    [int]$Port = 5173
)

$ErrorActionPreference = "Stop"

$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue

if (-not $connections) {
    Write-Host "No listening process found on port $Port."
    exit 0
}

$targets = $connections | Select-Object -ExpandProperty OwningProcess -Unique

Write-Host "Stopping processes on port ${Port}: $($targets -join ', ')"
Stop-Process -Id $targets -Force -ErrorAction SilentlyContinue

Write-Host "Done."
