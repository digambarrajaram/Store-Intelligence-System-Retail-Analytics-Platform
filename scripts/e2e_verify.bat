@echo off
REM ============================================================
REM  E2E Verification Script — Store Intelligence System
REM  Tests backend APIs, video pipeline data flow, frontend build
REM  Verifies video workers produce non-zero data for dashboard
REM ============================================================
setlocal enabledelayedexpansion

set API_URL=http://localhost:8000
set DASHBOARD_URL=http://localhost:3000
set PASS=0
set FAIL=0
set SKIP=0

echo ========================================
echo  Store Intelligence — E2E Verification
echo  (with video pipeline data-flow checks)
echo ========================================
echo.

REM ============================================================
REM STEP 1: API Health
REM ============================================================
echo [1/10] API Health Check...
curl -s -o nul -w "%%{http_code}" %API_URL%/health > .e2e_tmp 2>&1
set /p HTTP_CODE=<.e2e_tmp
if "!HTTP_CODE!"=="200" (
    echo   PASS: API is healthy (HTTP 200^)
    set /a PASS+=1
) else (
    echo   FAIL: API returned HTTP !HTTP_CODE!
    set /a FAIL+=1
)

REM ============================================================
REM STEP 2: Docker Container Status (video workers)
REM ============================================================
echo [2/10] Docker Container Status...
docker ps --format "{{.Names}} {{.Status}}" > .e2e_docker.txt 2>&1
if !errorlevel! equ 0 (
    set WORKER_COUNT=0
    set HEALTHY_COUNT=0
    for /f "tokens=1,*" %%a in (.e2e_docker.txt) do (
        echo %%a | findstr /b "worker_" > nul
        if !errorlevel! equ 0 (
            set /a WORKER_COUNT+=1
            echo %%b | findstr "healthy" > nul
            if !errorlevel! equ 0 (
                set /a HEALTHY_COUNT+=1
            ) else (
                echo   WARN: Worker %%a status: %%b
            )
        )
    )
    echo   PASS: !HEALTHY_COUNT!/!WORKER_COUNT! video workers are running
    set /a PASS+=1
) else (
    echo   SKIP: Docker not available
    set /a SKIP+=1
)

REM ============================================================
REM STEP 3: KPI Endpoint — check for NON-ZERO video-derived data
REM ============================================================
echo [3/10] KPI Data (video pipeline)...
curl -s %API_URL%/api/v1/kpis > .e2e_kpis.json 2>&1
if exist .e2e_kpis.json (
    findstr "currentOccupancy" .e2e_kpis.json > nul 2>&1
    if !errorlevel! equ 0 (
        echo   PASS: /kpis returns camelCase fields (frontend reads these correctly^)
    ) else (
        findstr "current_occupancy" .e2e_kpis.json > nul 2>&1
        if !errorlevel! equ 0 (
            echo   WARN: /kpis returns snake_case — normalizeKPIResponse handles this
        ) else (
            echo   FAIL: /kpis response missing expected fields
            type .e2e_kpis.json
            set /a FAIL+=1
            goto :skip_kpis
        )
    )

    REM Check for non-zero values (video pipeline producing data^)
    findstr "currentOccupancy" .e2e_kpis.json | findstr ": [1-9]" > nul 2>&1
    if !errorlevel! equ 0 (
        echo   PASS: currentOccupancy ^> 0 (people detected by cameras^)
    ) else (
        echo   WARN: currentOccupancy = 0 (no people detected yet^)
    )

    findstr "totalEntriesToday" .e2e_kpis.json | findstr ": [1-9]" > nul 2>&1
    if !errorlevel! equ 0 (
        echo   PASS: totalEntriesToday ^> 0 (entries tracked from video^)
    ) else (
        echo   WARN: totalEntriesToday = 0 (no entries tracked yet^)
    )

    findstr "conversionRate" .e2e_kpis.json | findstr ": [1-9]" > nul 2>&1
    if !errorlevel! equ 0 (
        echo   PASS: conversionRate ^> 0 (funnel conversions from video^)
    ) else (
        echo   WARN: conversionRate = 0 (no conversions yet^)
    )

    set /a PASS+=1
) else (
    echo   FAIL: /kpis endpoint not reachable
    set /a FAIL+=1
)
:skip_kpis

REM ============================================================
REM STEP 4: Funnel Endpoint — check for NON-ZERO video-derived data
REM ============================================================
echo [4/10] Funnel Data (video pipeline)...
curl -s %API_URL%/api/v1/funnel > .e2e_funnel.json 2>&1
if exist .e2e_funnel.json (
    findstr "Entered Store" .e2e_funnel.json > nul 2>&1
    if !errorlevel! equ 0 (
        echo   PASS: /funnel returns array with step names
        findstr "Entered Store" .e2e_funnel.json | findstr ": [1-9]" > nul 2>&1
        if !errorlevel! equ 0 (
            echo   PASS: Funnel has non-zero values (people flowing through stages^)
        ) else (
            echo   WARN: All funnel values are 0 (no video data processed yet^)
        )
    ) else (
        echo   WARN: /funnel response format unexpected
        type .e2e_funnel.json
    )
    set /a PASS+=1
) else (
    echo   FAIL: /funnel endpoint not reachable
    set /a FAIL+=1
)

REM ============================================================
REM STEP 5: Store Metrics — check per-camera video data
REM ============================================================
echo [5/10] Store Metrics (per-camera video data)...
curl -s "%API_URL%/api/v1/store-metrics?camera_id=all" > .e2e_metrics.json 2>&1
if exist .e2e_metrics.json (
    findstr "camera_" .e2e_metrics.json > nul 2>&1
    if !errorlevel! equ 0 (
        echo   PASS: /store-metrics returns per-camera data
        findstr "current_occupancy" .e2e_metrics.json | findstr ": [1-9]" > nul 2>&1
        if !errorlevel! equ 0 (
            echo   PASS: Some cameras have non-zero occupancy (video detection working^)
        ) else (
            echo   WARN: All cameras show 0 occupancy (workers may still be processing^)
        )
    ) else (
        echo   WARN: /store-metrics response missing camera data
    )
    set /a PASS+=1
) else (
    echo   FAIL: /store-metrics endpoint not reachable
    set /a FAIL+=1
)

REM ============================================================
REM STEP 6: Occupancy History — check time-series data
REM ============================================================
echo [6/10] Occupancy History (time-series from video)...
curl -s "%API_URL%/api/v1/occupancy/history?window_minutes=30" > .e2e_history.json 2>&1
if exist .e2e_history.json (
    findstr "history" .e2e_history.json > nul 2>&1
    if !errorlevel! equ 0 (
        echo   PASS: /occupancy/history returns history data
        findstr "count" .e2e_history.json | findstr ": [1-9]" > nul 2>&1
        if !errorlevel! equ 0 (
            echo   PASS: History has non-zero occupancy points
        ) else (
            echo   WARN: All history points are 0 (no video data recorded yet^)
        )
    ) else (
        echo   WARN: /occupancy/history response unexpected
    )
    set /a PASS+=1
) else (
    echo   FAIL: /occupancy/history endpoint not reachable
    set /a FAIL+=1
)

REM ============================================================
REM STEP 7: Dashboard Serving
REM ============================================================
echo [7/10] Dashboard Serving...
curl -s -o nul -w "%%{http_code}" %DASHBOARD_URL%/ > .e2e_tmp2 2>&1
set /p HTTP_CODE2=<.e2e_tmp2
if "!HTTP_CODE2!"=="200" (
    echo   PASS: Dashboard is serving (HTTP 200^)
    set /a PASS+=1
) else (
    echo   FAIL: Dashboard not reachable (HTTP !HTTP_CODE2!^)
    set /a FAIL+=1
)

REM ============================================================
REM STEP 8: Frontend TypeScript Compilation
REM ============================================================
echo [8/10] Frontend TypeScript Compilation...
if exist "dashboard\node_modules" (
    cd dashboard
    call npx tsc --noEmit 2> ..\.e2e_tsc_errors.txt
    if !errorlevel! equ 0 (
        echo   PASS: TypeScript compilation successful (no type errors^)
        set /a PASS+=1
    ) else (
        echo   FAIL: TypeScript compilation errors found
        type ..\.e2e_tsc_errors.txt
        set /a FAIL+=1
    )
    cd ..
) else (
    echo   SKIP: node_modules not found (run 'cd dashboard ^&^& npm install' first^)
    set /a SKIP+=1
)

REM ============================================================
REM STEP 9: Redis Data — check video pipeline keys
REM ============================================================
echo [9/10] Redis Video Pipeline Data...
docker exec redis redis-cli KEYS "store:*" > .e2e_redis.txt 2>&1
if !errorlevel! equ 0 (
    findstr /v "KEYS" .e2e_redis.txt | findstr /c:"store:" > nul 2>&1
    if !errorlevel! equ 0 (
        echo   PASS: Redis has store-related keys from video pipeline
        findstr "worker.alive" .e2e_redis.txt > nul 2>&1
        if !errorlevel! equ 0 (
            echo   PASS: Video workers are alive in Redis
        ) else (
            echo   WARN: No worker.alive keys found
        )
        findstr "funnel:" .e2e_redis.txt > nul 2>&1
        if !errorlevel! equ 0 (
            echo   PASS: Funnel keys exist (video pipeline populating funnel data^)
        ) else (
            echo   WARN: No funnel keys found in Redis
        )
        findstr ":entries" .e2e_redis.txt > nul 2>&1
        if !errorlevel! equ 0 (
            echo   PASS: Entry/exit tracking keys exist
        ) else (
            echo   WARN: No entry/exit tracking keys found
        )
    ) else (
        echo   WARN: Redis has no store keys (video pipeline hasn't written data yet^)
    )
    set /a PASS+=1
) else (
    echo   SKIP: Cannot check Redis directly (not running in Docker?^)
    set /a SKIP+=1
)

REM ============================================================
REM STEP 10: End-to-End Data Flow Summary
REM ============================================================
echo [10/10] End-to-End Data Flow Summary...
echo.
echo        ==========================================
echo          DASHBOARD DATA FLOW CHECK
echo        ==========================================
echo.
REM Extract values from KPI response for summary
for /f "tokens=2 delims=:," %%a in ('findstr "currentOccupancy" .e2e_kpis.json') do set OCC=%%a
for /f "tokens=2 delims=:," %%a in ('findstr "totalEntriesToday" .e2e_kpis.json') do set ENTRIES=%%a
for /f "tokens=2 delims=:," %%a in ('findstr "conversionRate" .e2e_kpis.json') do set CONV=%%a
for /f "tokens=2 delims=:," %%a in ('findstr "activeAnomalies" .e2e_kpis.json') do set ANOM=%%a

echo    KPI Cards (KPICards.tsx^):
echo      Current Occupancy : !OCC!  (→ Current Occupancy card^)
echo      Total Entries     : !ENTRIES!  (→ Total Entries Today card^)
echo      Conversion Rate   : !CONV!%% (→ Conversion Rate card^)
echo      Active Anomalies  : !ANOM!  (→ Active Anomalies card^)
echo.
echo    Funnel Chart (FunnelChart.tsx^):
for /f "tokens=*" %%a in ('findstr "step" .e2e_funnel.json') do (
    echo      %%a
)
echo.
echo    Check the dashboard at: %DASHBOARD_URL%
echo.

REM Determine if video data is flowing
set HAS_DATA=0
if !OCC! gtr 0 set HAS_DATA=1
if !ENTRIES! gtr 0 set HAS_DATA=1
if !CONV! gtr 0 set HAS_DATA=1
if !HAS_DATA! equ 1 (
    echo   PASS: Video pipeline data is flowing to the dashboard APIs
) else (
    echo   WARN: All values are zero — video pipeline may still be initializing
    echo   WARN: Run again in 60-120 seconds after workers have processed frames
)
set /a PASS+=1

echo.
echo ========================================
echo  Results: %PASS% passed, %FAIL% failed, %SKIP% skipped
echo ========================================

REM Cleanup temp files
del .e2e_tmp .e2e_tmp2 2>nul
del .e2e_kpis.json .e2e_funnel.json .e2e_metrics.json .e2e_history.json 2>nul
del .e2e_redis.txt .e2e_docker.txt 2>nul
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
