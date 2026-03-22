@echo off
REM Ultra-Quick Install Script for Windows
REM Gets you running in under 5 minutes

echo ======================================================================
echo   Purple Pipeline Parser Eater - Ultra-Quick Setup
echo ======================================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

echo [1/5] Installing CORE packages (anthropic, aiohttp, pyyaml)...
pip install anthropic aiohttp pyyaml structlog --quiet
if errorlevel 1 (
    echo ERROR: Package installation failed
    pause
    exit /b 1
)
echo       Done!
echo.

echo [2/5] Creating config.yaml from example...
if not exist config.yaml (
    copy config.yaml.example config.yaml >nul
    echo       Created config.yaml
) else (
    echo       config.yaml already exists
)
echo.

echo [3/5] Creating output directories...
if not exist output mkdir output
if not exist logs mkdir logs
echo       Done!
echo.

echo [4/5] Testing imports...
python -c "from orchestrator import ConversionSystemOrchestrator" 2>nul
if errorlevel 1 (
    echo       WARNING: Some imports failed
    echo       Installing additional packages...
    pip install tenacity pandas jsonschema python-dotenv click prometheus-client --quiet
)
echo       Done!
echo.

echo [5/5] Final check...
python -c "import anthropic, aiohttp, yaml; print('  All core packages ready!')"
echo.

echo ======================================================================
echo   Setup Complete!
echo ======================================================================
echo.
echo NEXT STEPS:
echo.
echo 1. Get your Anthropic API key from: https://console.anthropic.com/
echo.
echo 2. Edit config.yaml and add your API key:
echo    notepad config.yaml
echo.
echo    Change this line:
echo      api_key: "your-anthropic-api-key-here"
echo    To your actual key:
echo      api_key: "sk-ant-YOUR-ACTUAL-KEY"
echo.
echo 3. Test with dry-run (no API calls):
echo    python main.py --dry-run --max-parsers 1 --verbose
echo.
echo 4. Run for real (needs API key):
echo    python main.py --max-parsers 5 --parser-types community
echo.
echo For help: See README.md and WHAT_YOU_ACTUALLY_NEED.md
echo.
pause
