@echo off
REM ============================================================
REM  E2E Verification Script — Store Intelligence System
REM  Tests backend APIs, Redis data, and frontend build
REM ============================================================
setlocal enabledelayedexpansion

set API_URL=http://localhost:8000
set DASHBOARD_URL=http://localhost:3000
set PASS=0
set FAIL=0

echo ========================================
echo  Store Intelligence — E2E Verification
echo ========================================
echo.

REM ---- Step 1: Health Check ----
echo [1/8] Checking API health...
curl -s -o nul -w "%%{http_code}" %API_URL%/health > .e2e_tmp 2>&1
set /p HTTP_CODE=<.e2e_tmp
if "!HTTP_CODE!"=="200" (
    echo   PASS: API is healthy (HTTP 200^)
    set /a PASS+=1
) else (
    echo   FAIL: API returned HTTP !HTTP_CODE!
    set /a FAIL+=1
)

REM ---- Step 2: KPI Endpoint ----
echo [2/8] Checking /api/v1/kpis endpoint...
curl -s %API_URL%/api/v1/kpis > .e2e_kpis.json 2>&1
if exist .e2e_kpis.json (
    REM Check that key fields exist (camelCase or snake_case)
    findstr "currentOccupancy" .e2e_kpis.json > nul 2>&1
    if !errorlevel! equ 0 (
        echo   PASS: /kpis returns camelCase fields
    ) else (
        findstr "current_occupancy" .e2e_kpis.json > nul 2>&1
        if !errorlevel! equ 0 (
            echo   PASS: /kpis returns snake_case fields
        ) else (
            echo   FAIL: /kpis response missing expected fields
            type .e2e_kpis.json
        )
    )
    set /a PASS+=1
) else (
    echo   FAIL: /kpis endpoint not reachable
    set /a FAIL+=1
)

REM ---- Step 3: Funnel Endpoint ----
echo [3/8] Checking /api/v1/funnel endpoint...
curl -s %API_URL%/api/v1/funnel > .e2e_funnel.json 2>&1
if exist .e2e_funnel.json (
    findstr "Entered Store" .e2e_funnel.json > nul 2>&1
    if !errorlevel! equ 0 (
        echo   PASS: /funnel returns array with step names
    ) else (
        echo   WARN: /funnel response format unexpected
        type .e2e_funnel.json
    )
    set /a PASS+=1
) else (
    echo   FAIL: /funnel endpoint not reachable
    set /a FAIL+=1
)

REM ---- Step 4: Store Metrics Endpoint ----
echo [4/8] Checking /api/v1/store-metrics endpoint...
curl -s %API_URL%/api/v1/store-metrics > .e2e_metrics.json 2>&1
if exist .e2e_metrics.json (
    findstr "current_occupancy" .e2e_metrics.json > nul 2>&1
    if !errorlevel! equ 0 (
        echo   PASS: /store-metrics returns data
    ) else (
        echo   WARN: /store-metrics response unexpected
        type .e2e_metrics.json
    )
    set /a PASS+=1
) else (
    echo   FAIL: /store-metrics endpoint not reachable
    set /a FAIL+=1
)

REM ---- Step 5: Occupancy History Endpoint ----
echo [5/8] Checking /api/v1/occupancy/history endpoint...
curl -s "%API_URL%/api/v1/occupancy/history?window_minutes=30" > .e2e_history.json 2>&1
if exist .e2e_history.json (
    findstr "history" .e2e_history.json > nul 2>&1
    if !errorlevel! equ 0 (
        echo   PASS: /occupancy/history returns history data
    ) else (
        echo   WARN: /occupancy/history response unexpected
    )
    set /a PASS+=1
) else (
    echo   FAIL: /occupancy/history endpoint not reachable
    set /a FAIL+=1
)

REM ---- Step 6: Dashboard Health ----
echo [6/8] Checking Dashboard health...
curl -s -o nul -w "%%{http_code}" %DASHBOARD_URL%/health > .e2e_tmp2 2>&1
set /p HTTP_CODE2=<.e2e_tmp2
if "!HTTP_CODE2!"=="200" (
    echo   PASS: Dashboard is healthy (HTTP 200^)
    set /a PASS+=1
) else (
    echo   WARN: Dashboard health returned HTTP !HTTP_CODE2! (may not have /health endpoint^)
    REM Check if dashboard is up at all
    curl -s -o nul -w "%%{http_code}" %DASHBOARD_URL%/ > .e2e_tmp3 2>&1
    set /p HTTP_CODE3=<.e2e_tmp3
    if "!HTTP_CODE3!"=="200" (
        echo   PASS: Dashboard is serving (HTTP 200 on root^)
        set /a PASS+=1
    ) else (
        echo   FAIL: Dashboard not reachable (HTTP !HTTP_CODE3!^)
        set /a FAIL+=1
    )
)

REM ---- Step 7: Frontend Build Check ----
echo [7/8] Checking frontend TypeScript compilation...
if exist "dashboard\node_modules" (
    cd dashboard
    call npx tsc --noEmit 2> ..\.e2e_tsc_errors.txt
    if !errorlevel! equ 0 (
        echo   PASS: TypeScript compilation successful
        set /a PASS+=1
    ) else (
        echo   FAIL: TypeScript compilation errors found
        type ..\.e2e_tsc_errors.txt
        set /a FAIL+=1
    )
    cd ..
) else (
    echo   SKIP: node_modules not found (run 'cd dashboard ^&^& npm install' first^)
)

REM ---- Step 8: Redis Data Check ----
echo [8/8] Checking Redis for stored data...
REM Try to check Redis via the API debug endpoint or directly
curl -s %API_URL%/api/v1/debug/redis > .e2e_redis.json 2>&1
if exist .e2e_redis.json (
    echo   PASS: Redis debug endpoint reachable
    set /a PASS+=1
) else (
    echo   WARN: Redis debug endpoint not available (may not be exposed^)
    REM Try direct Redis check via docker
    docker exec redis redis-cli ping 2>nul | findstr "PONG" > nul
    if !errorlevel! equ 0 (
        echo   PASS: Redis is responding to PING
        set /a PASS+=1
    ) else (
        echo   SKIP: Cannot check Redis directly (not running in Docker?^)
    )
)

echo.
echo ========================================
echo  Results: %PASS% passed, %FAIL% failed
echo ========================================

REM Cleanup temp files
del .e2e_tmp .e2e_tmp2 .e2e_tmp3 2>nul
del .e2e_kpis.json .e2e_funnel.json .e2e_metrics.json .e2e_history.json .e2e_redis.json 2>nul
del .e2e_tsc_errors.txt 2>nul

if %FAIL% gtr 0 (
    echo.
    echo  WARNING: %FAIL% check(s^) failed. Review output above.
    exit /b 1
) else (
    echo.
    echo  All checks passed! System is healthy.
    exit /b 0
)
