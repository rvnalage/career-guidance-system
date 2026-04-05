param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue

if (-not $connections) {
    Write-Host "No listening process found on port $Port."
    exit 0
}

$targets = $connections | Select-Object -ExpandProperty OwningProcess -Unique

$targets | ForEach-Object {
    Write-Host "Stopping process on port ${Port}: $_"
    Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
}

Write-Host "Done."
