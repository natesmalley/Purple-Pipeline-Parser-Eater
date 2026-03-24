# Purple Pipeline Parser Eater - Web UI Authentication Setup Script (PowerShell)
# Sets the WEB_UI_AUTH_TOKEN environment variable for Web UI authentication
# Run: powershell -ExecutionPolicy Bypass -File scripts/setup_web_ui_auth.ps1

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Purple Pipeline Parser Eater - Web UI Authentication Setup" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if token is already set
if ($env:WEB_UI_AUTH_TOKEN) {
    Write-Host "[OK] WEB_UI_AUTH_TOKEN is already set" -ForegroundColor Green
    $shortToken = $env:WEB_UI_AUTH_TOKEN.Substring(0, 20)
    Write-Host "Token (first 20 chars): $shortToken..." -ForegroundColor Green
    Write-Host ""
    Write-Host "Run: python main.py" -ForegroundColor Yellow
    exit 0
}

# Token to set (generated 2025-11-07)
$token = "lcPl4R6CE_3C02oQZ5opRgdt-OqIXOn8tB-tYscTDQw"

Write-Host "Setting WEB_UI_AUTH_TOKEN environment variable..." -ForegroundColor Yellow
Write-Host ""

# Set for current session
$env:WEB_UI_AUTH_TOKEN = $token

# Set permanently for current user
[Environment]::SetEnvironmentVariable("WEB_UI_AUTH_TOKEN", $token, [EnvironmentVariableTarget]::User)

Write-Host "[OK] Environment variable set successfully" -ForegroundColor Green
Write-Host ""
Write-Host "Token: $token" -ForegroundColor Green
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  SUCCESS - Token set in current session and user environment" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Run: python main.py" -ForegroundColor White
Write-Host "  2. Access Web UI at: http://localhost:8080/" -ForegroundColor White
Write-Host "  3. Use header: X-PPPE-Token: $token" -ForegroundColor White
Write-Host ""
Write-Host "Verification:" -ForegroundColor Yellow
Write-Host "  curl -H 'X-PPPE-Token: $token' http://localhost:8080/" -ForegroundColor White
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
