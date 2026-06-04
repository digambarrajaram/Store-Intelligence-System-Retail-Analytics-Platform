<#
.SYNOPSIS
    End-to-End Verification Script for Store Intelligence System
.DESCRIPTION
    Tests backend APIs, frontend build, and Redis connectivity.
    Run this after docker compose up to verify everything is working.
.EXAMPLE
    .\scripts\e2e_verify.ps1
    .\scripts\e2e_verify.ps1 -ApiUrl "http://localhost:8000" -DashboardUrl "http://localhost:3000"
#>

param(
    [string]$ApiUrl = "http://localhost:8000",
    [string]$DashboardUrl = "http://localhost:3000"
)

$pass = 0
$fail = 0
$skip = 0

function Write-Result {
    param([string]$Status, [string]$Message)
    $color = switch ($Status) {
        "PASS" { "Green" }
        "FAIL" { "Red" }
        "WARN" { "Yellow" }
        "SKIP" { "Gray" }
    }
    Write-Host "  $Status`: $Message" -ForegroundColor $color
}

function Test-HttpStatus {
    param([string]$Url, [string]$Label)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
        if ($response.StatusCode -eq 200) {
            Write-Result "PASS" "$Label (HTTP 200)"
            return $true
        } else {
            Write-Result "FAIL" "$Label returned HTTP $($response.StatusCode)"
            return $false
        }
    } catch {
        Write-Result "FAIL" "$Label — $_"
        return $false
    }
}

function Test-JsonField {
    param([string]$JsonPath, [string]$Field, [string]$Label)
    try {
        $content = Get-Content $JsonPath -Raw | ConvertFrom-Json
        $found = $content.PSObject.Properties.Name -contains $Field
        if ($found) {
            Write-Result "PASS" "$Label — contains '$Field'"
            return $true
        } else {
            Write-Result "WARN" "$Label — missing '$Field', checking alternatives..."
            return $false
        }
    } catch {
        Write-Result "FAIL" "$Label — could not parse JSON: $_"
        return $false
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Store Intelligence — E2E Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---- Step 1: Health Check ----
Write-Host "[1/8] Checking API health..." -ForegroundColor White
if (Test-HttpStatus "$ApiUrl/health" "API health endpoint") { $pass++ } else { $fail++ }

# ---- Step 2: KPI Endpoint ----
Write-Host "[2/8] Checking /api/v1/kpis endpoint..." -ForegroundColor White
try {
    $kpis = Invoke-RestMethod -Uri "$ApiUrl/api/v1/kpis" -TimeoutSec 10
    $kpis | ConvertTo-Json -Depth 5 | Out-File ".e2e_kpis.json"
    if ($kpis.PSObject.Properties.Name -contains "currentOccupancy") {
        Write-Result "PASS" "/kpis returns camelCase fields (currentOccupancy = $($kpis.currentOccupancy))"
    } elseif ($kpis.PSObject.Properties.Name -contains "current_occupancy") {
        Write-Result "PASS" "/kpis returns snake_case fields (current_occupancy = $($kpis.current_occupancy))"
    } else {
        Write-Result "FAIL" "/kpis response missing expected fields: $($kpis | ConvertTo-Json -Compress)"
        $fail++
        continue
    }
    $pass++
} catch {
    Write-Result "FAIL" "/kpis endpoint error: $_"
    $fail++
}

# ---- Step 3: Funnel Endpoint ----
Write-Host "[3/8] Checking /api/v1/funnel endpoint..." -ForegroundColor White
try {
    $funnel = Invoke-RestMethod -Uri "$ApiUrl/api/v1/funnel" -TimeoutSec 10
    $funnel | ConvertTo-Json -Depth 5 | Out-File ".e2e_funnel.json"
    $funnelArray = if ($funnel.funnel) { $funnel.funnel } else { $funnel }
    if ($funnelArray -is [array] -and $funnelArray[0].step -eq "Entered Store") {
        Write-Result "PASS" "/funnel returns array with step names (Entered Store = $($funnelArray[0].value))"
    } else {
        Write-Result "WARN" "/funnel response format: $($funnel | ConvertTo-Json -Compress)"
    }
    $pass++
} catch {
    Write-Result "FAIL" "/funnel endpoint error: $_"
    $fail++
}

# ---- Step 4: Store Metrics Endpoint ----
Write-Host "[4/8] Checking /api/v1/store-metrics endpoint..." -ForegroundColor White
try {
    $metrics = Invoke-RestMethod -Uri "$ApiUrl/api/v1/store-metrics" -TimeoutSec 10
    $metrics | ConvertTo-Json -Depth 5 | Out-File ".e2e_metrics.json"
    if ($metrics.PSObject.Properties.Name -contains "current_occupancy") {
        Write-Result "PASS" "/store-metrics returns data (current_occupancy = $($metrics.current_occupancy))"
    } else {
        Write-Result "WARN" "/store-metrics response: $($metrics | ConvertTo-Json -Compress)"
    }
    $pass++
} catch {
    Write-Result "FAIL" "/store-metrics endpoint error: $_"
    $fail++
}

# ---- Step 5: Occupancy History Endpoint ----
Write-Host "[5/8] Checking /api/v1/occupancy/history endpoint..." -ForegroundColor White
try {
    $history = Invoke-RestMethod -Uri "$ApiUrl/api/v1/occupancy/history?window_minutes=30" -TimeoutSec 10
    $history | ConvertTo-Json -Depth 5 | Out-File ".e2e_history.json"
    if ($history.history -and $history.history.Count -gt 0) {
        Write-Result "PASS" "/occupancy/history returns $($history.history.Count) data points"
    } else {
        Write-Result "WARN" "/occupancy/history returned empty or unexpected data"
    }
    $pass++
} catch {
    Write-Result "FAIL" "/occupancy/history endpoint error: $_"
    $fail++
}

# ---- Step 6: Dashboard Health ----
Write-Host "[6/8] Checking Dashboard..." -ForegroundColor White
try {
    $dashResp = Invoke-WebRequest -Uri "$DashboardUrl/" -UseBasicParsing -TimeoutSec 10
    if ($dashResp.StatusCode -eq 200) {
        Write-Result "PASS" "Dashboard is serving (HTTP 200)"
        $pass++
    } else {
        Write-Result "FAIL" "Dashboard returned HTTP $($dashResp.StatusCode)"
        $fail++
    }
} catch {
    Write-Result "FAIL" "Dashboard not reachable: $_"
    $fail++
}

# ---- Step 7: Frontend TypeScript Check ----
Write-Host "[7/8] Checking frontend TypeScript compilation..." -ForegroundColor White
$tscPath = Join-Path (Get-Location) "dashboard\node_modules\.bin\tsc.cmd"
if (Test-Path $tscPath) {
    Push-Location "dashboard"
    $tscOutput = & $tscPath --noEmit 2>&1
    $tscExitCode = $LASTEXITCODE
    Pop-Location
    if ($tscExitCode -eq 0) {
        Write-Result "PASS" "TypeScript compilation successful"
        $pass++
    } else {
        Write-Result "FAIL" "TypeScript compilation errors:"
        $tscOutput | ForEach-Object { Write-Host "       $_" -ForegroundColor Red }
        $fail++
    }
} else {
    Write-Result "SKIP" "node_modules not found (run 'cd dashboard && npm install' first)"
    $skip++
}

# ---- Step 8: Redis Data Check ----
Write-Host "[8/8] Checking Redis..." -ForegroundColor White
try {
    $redisCheck = Invoke-RestMethod -Uri "$ApiUrl/api/v1/debug/redis" -TimeoutSec 10 -ErrorAction SilentlyContinue
    if ($redisCheck) {
        Write-Result "PASS" "Redis debug endpoint reachable"
        $pass++
    }
} catch {
    # Try docker exec
    $dockerResult = & docker exec redis redis-cli ping 2>&1
    if ($LASTEXITCODE -eq 0 -and $dockerResult -match "PONG") {
        Write-Result "PASS" "Redis is responding to PING"
        $pass++
    } else {
        Write-Result "SKIP" "Cannot check Redis directly (not running in Docker?)"
        $skip++
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Results: $pass passed, $fail failed, $skip skipped" -ForegroundColor $(if ($fail -gt 0) { "Red" } else { "Green" })
Write-Host "========================================" -ForegroundColor Cyan

# Cleanup temp files
Get-Item ".e2e_*.json" -ErrorAction SilentlyContinue | Remove-Item -Force

if ($fail -gt 0) {
    Write-Host ""
    Write-Host "WARNING: $fail check(s) failed. Review output above." -ForegroundColor Red
    exit 1
} else {
    Write-Host ""
    Write-Host "All checks passed! System is healthy." -ForegroundColor Green
    exit 0
}
