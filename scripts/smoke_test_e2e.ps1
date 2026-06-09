# End-to-end smoke test: boot the server, hit every public endpoint,
# verify auth + RBAC, tear server down.
# Results table written to stdout, suitable for the SysRS audit doc.

$ErrorActionPreference = "Continue"
$base = "http://127.0.0.1:5000"

function Result($name, $status, $detail = "") {
    "{0,-50} {1,-6} {2}" -f $name, $status, $detail
}

$env:PYTHONIOENCODING = "utf-8"
$proc = Start-Process -FilePath ".\venv\Scripts\python.exe" `
    -ArgumentList "server_app.py" -PassThru `
    -RedirectStandardOutput "logs\_smoke.log" -RedirectStandardError "logs\_smoke.err"

# Wait for /api/health (max 8s)
$ready = $false
for ($i = 0; $i -lt 16; $i++) {
    try {
        $h = Invoke-RestMethod -Uri "$base/api/health" -ErrorAction SilentlyContinue -TimeoutSec 1
        if ($h.status -eq "ok") { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}

if (-not $ready) {
    Write-Host "SERVER FAILED TO START - see logs\_smoke.err"
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host ""
Write-Host "Endpoint                                          Status Detail"
Write-Host ("-" * 78)
Write-Host (Result "GET  /api/health" "200" "server up")

# Login admin
try {
    $login = Invoke-RestMethod -Uri "$base/api/staff/login" -Method Post `
        -Body (@{username='admin'; password='admin123'} | ConvertTo-Json) `
        -ContentType 'application/json'
    Write-Host (Result "POST /api/staff/login (admin)" "200" "role=$($login.staff.role)")
    $tok = $login.access_token
    $hdr = @{Authorization="Bearer $tok"}
} catch {
    Write-Host (Result "POST /api/staff/login (admin)" "FAIL" $_.Exception.Message)
    Stop-Process -Id $proc.Id -Force
    exit 1
}

# Login receptionist
$recHdr = $null
try {
    $rl = Invoke-RestMethod -Uri "$base/api/staff/login" -Method Post `
        -Body (@{username='receptionist'; password='reception123'} | ConvertTo-Json) `
        -ContentType 'application/json'
    Write-Host (Result "POST /api/staff/login (receptionist)" "200" "role=$($rl.staff.role)")
    $recHdr = @{Authorization="Bearer $($rl.access_token)"}
} catch {
    Write-Host (Result "POST /api/staff/login (receptionist)" "FAIL" $_.Exception.Message)
}

# Auth-gated reads
$endpoints = @(
    "GET /api/guests/",
    "GET /api/guests/vip",
    "GET /api/guests/search?name=a",
    "GET /api/staff/",
    "GET /api/alerts/",
    "GET /api/alerts/pending",
    "GET /api/services/",
    "GET /api/services/active",
    "GET /api/reservations/",
    "GET /api/visits/",
    "GET /api/recommendations/",
    "GET /api/monitoring/status",
    "GET /api/system/status",
    "GET /api/system/stats"
)

foreach ($ep in $endpoints) {
    try {
        $url = $base + ($ep -replace "^GET\s+", "")
        $resp = Invoke-WebRequest -Uri $url -Headers $hdr -UseBasicParsing -ErrorAction Stop
        Write-Host (Result $ep $resp.StatusCode "")
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        if (-not $code) { $code = "ERR" }
        Write-Host (Result $ep "$code" $_.Exception.Message)
    }
}

# Auth required (no token = 401)
try {
    Invoke-WebRequest -Uri "$base/api/guests/" -UseBasicParsing -ErrorAction Stop | Out-Null
    Write-Host (Result "GET /api/guests/ (no token)" "200" "AUTH NOT ENFORCED - BUG")
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    Write-Host (Result "GET /api/guests/ (no token)" "$code" "auth enforced")
}

# RBAC: receptionist tries admin-only stats
if ($recHdr) {
    try {
        Invoke-WebRequest -Uri "$base/api/system/stats" -Headers $recHdr -UseBasicParsing -ErrorAction Stop | Out-Null
        Write-Host (Result "GET /api/system/stats (receptionist)" "200" "RBAC NOT ENFORCED - BUG")
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        Write-Host (Result "GET /api/system/stats (receptionist)" "$code" "RBAC enforced")
    }
}

# Edge ingest with X-API-Key
$apiKey = ""
if (Test-Path .env) {
    $line = (Get-Content .env | Where-Object { $_ -match '^API_KEY=' })
    if ($line) { $apiKey = ($line -replace '^API_KEY=', '').Trim() }
}
if ($apiKey) {
    try {
        $resp = Invoke-WebRequest -Uri "$base/api/edge/heartbeat" `
            -Headers @{"X-API-Key"=$apiKey} -UseBasicParsing -ErrorAction Stop
        Write-Host (Result "GET /api/edge/heartbeat (X-API-Key)" $resp.StatusCode "ok")
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        Write-Host (Result "GET /api/edge/heartbeat (X-API-Key)" "$code" $_.Exception.Message)
    }
} else {
    Write-Host (Result "GET /api/edge/heartbeat (X-API-Key)" "SKIP" "API_KEY not in .env")
}

# Edge ingest without key = 401
try {
    Invoke-WebRequest -Uri "$base/api/edge/heartbeat" -UseBasicParsing -ErrorAction Stop | Out-Null
    Write-Host (Result "GET /api/edge/heartbeat (no key)" "200" "AUTH NOT ENFORCED - BUG")
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    Write-Host (Result "GET /api/edge/heartbeat (no key)" "$code" "API-key enforced")
}

# SPA index
try {
    $r = Invoke-WebRequest -Uri "$base/" -UseBasicParsing -ErrorAction Stop
    $hasTitle = $r.Content -match "Smart Reception"
    $detail = if ($hasTitle) { "SPA index served" } else { "served but no title match" }
    Write-Host (Result "GET /" $r.StatusCode $detail)
} catch {
    Write-Host (Result "GET /" "FAIL" $_.Exception.Message)
}

# OpenAPI docs
try {
    $r = Invoke-WebRequest -Uri "$base/docs" -UseBasicParsing -ErrorAction Stop
    Write-Host (Result "GET /docs (Swagger UI)" $r.StatusCode "")
} catch {
    Write-Host (Result "GET /docs (Swagger UI)" "FAIL" $_.Exception.Message)
}

Write-Host ""
Write-Host "Stopping server (PID $($proc.Id))..."
Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Write-Host "Smoke test complete."
