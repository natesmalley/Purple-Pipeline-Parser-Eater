@echo off
REM Purple Pipeline Parser Eater - Web UI Authentication Setup Script
REM Sets the WEB_UI_AUTH_TOKEN environment variable for Web UI authentication
REM Run this ONCE before first startup, then the token will be persistent

setlocal enabledelayedexpansion

echo.
echo ============================================================================
echo   Purple Pipeline Parser Eater - Web UI Authentication Setup
echo ============================================================================
echo.

REM Check if token is already set
if not "%WEB_UI_AUTH_TOKEN%"=="" (
    echo [OK] WEB_UI_AUTH_TOKEN is already set
    echo Token (first 20 chars): %WEB_UI_AUTH_TOKEN:~0,20%...
    echo.
    echo Run: python main.py
    exit /b 0
)

REM Token to set (generated 2025-11-07)
set "TOKEN=lcPl4R6CE_3C02oQZ5opRgdt-OqIXOn8tB-tYscTDQw"

echo Setting WEB_UI_AUTH_TOKEN environment variable...
echo.

REM Set for current session
setx WEB_UI_AUTH_TOKEN %TOKEN%

if %errorlevel% equ 0 (
    echo [OK] Environment variable set successfully
    echo.
    echo Token: %TOKEN%
    echo.
    echo ============================================================================
    echo   IMPORTANT: Open a NEW command prompt for the variable to take effect
    echo ============================================================================
    echo.
    echo Next steps:
    echo   1. Open a NEW command prompt or PowerShell window
    echo   2. Run: python main.py
    echo   3. Access Web UI at: http://localhost:8080/
    echo   4. Use header: X-PPPE-Token: %TOKEN%
    echo.
    echo ============================================================================
) else (
    echo [ERROR] Failed to set environment variable
    echo Run as Administrator and try again
    exit /b 1
)

endlocal
