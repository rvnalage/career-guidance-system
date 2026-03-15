param(
    [string]$ApiBaseUrl = "http://localhost:8000/api/v1",
    [string]$Token = "",
    [string]$OwnerType = "self",
    [string]$FilePath = ""
)

if (-not $Token) {
    Write-Host "Pass a bearer token using -Token <jwt>." -ForegroundColor Yellow
    exit 1
}

$headers = @{ Authorization = "Bearer $Token" }

Write-Host "[1/3] Sending chat message with structured profile context..." -ForegroundColor Cyan
$chatPayload = @{
    message                 = "Give me a learning roadmap for data engineering"
    context                 = @{}
    context_owner_type      = $OwnerType
    skills                  = @("python", "sql", "docker")
    interests               = @("data", "analytics")
    education_level         = "master"
    psychometric_dimensions = @{
        investigative = 5
        realistic     = 4
        artistic      = 3
        social        = 3
        enterprising  = 3
        conventional  = 4
    }
} | ConvertTo-Json -Depth 5

$chatResponse = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/chat/message/me" -Headers ($headers + @{ "Content-Type" = "application/json" }) -Body $chatPayload
$chatResponse | ConvertTo-Json -Depth 6

if ($FilePath -and (Test-Path $FilePath)) {
    Write-Host "[2/3] Uploading profile file for intake..." -ForegroundColor Cyan
    $fileName = Split-Path -Leaf $FilePath
    $boundary = [System.Guid]::NewGuid().ToString()
    $fileBytes = [System.IO.File]::ReadAllBytes($FilePath)
    $fileText = [System.Text.Encoding]::UTF8.GetString($fileBytes)

    $body = @(
        "--$boundary"
        "Content-Disposition: form-data; name=\"owner_type\""
        ""
        $OwnerType
        "--$boundary"
        "Content-Disposition: form-data; name=\"files\"; filename=\"$fileName\""
        "Content-Type: text/plain"
        ""
        $fileText
        "--$boundary--"
    ) -join "`r`n"

    $uploadHeaders = @{ Authorization = "Bearer $Token"; "Content-Type" = "multipart/form-data; boundary=$boundary" }
    $uploadResponse = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/profile-intake/upload" -Headers $uploadHeaders -Body $body
    $uploadResponse | ConvertTo-Json -Depth 6
}
else {
    Write-Host "[2/3] Skipping upload. Provide -FilePath <path-to-text-file> to test file intake." -ForegroundColor DarkYellow
}

Write-Host "[3/3] Triggering recommendation generation..." -ForegroundColor Cyan
$recommendationPayload = @{
    interests       = @("data", "analytics", "ai")
    skills          = @("python", "sql", "docker")
    education_level = "master"
} | ConvertTo-Json -Depth 4

$recommendationResponse = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/recommendations/generate" -Headers ($headers + @{ "Content-Type" = "application/json" }) -Body $recommendationPayload
$recommendationResponse | ConvertTo-Json -Depth 6

Write-Host "Done. Manual profile-context flow executed." -ForegroundColor Green
