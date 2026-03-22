@echo off
REM ============================================================================
REM Purple Pipeline Parser Eater - Quick Start Script (Windows)
REM ============================================================================

echo ======================================================================
echo.
echo          Purple Pipeline Parser Eater - Quick Start
echo.
echo ======================================================================
echo.

REM Check Python version
echo Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8 or higher.
    pause
    exit /b 1
)
echo Python found
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created
) else (
    echo Virtual environment already exists
)
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo Virtual environment activated
echo.

REM Install dependencies
echo Installing dependencies...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
echo Dependencies installed
echo.

REM Check if config.yaml exists
if not exist "config.yaml" (
    echo Creating config.yaml from example...
    if exist "config.yaml.example" (
        copy config.yaml.example config.yaml >nul
        echo config.yaml created
        echo.
        echo IMPORTANT: Edit config.yaml and add your API keys:
        echo    - Anthropic API key (Claude^)
        echo    - Observo.ai API key
        echo    - GitHub token (optional^)
        echo.
        echo Press any key to open config.yaml in notepad...
        pause >nul
        notepad config.yaml
    ) else (
        echo ERROR: config.yaml.example not found
        pause
        exit /b 1
    )
) else (
    echo config.yaml already exists
)
echo.

REM Verify configuration
echo Verifying configuration...
python -c "import yaml; yaml.safe_load(open('config.yaml'))" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Configuration file has syntax errors
    pause
    exit /b 1
)
echo Configuration file is valid
echo.

REM Create output directories
if not exist "output" mkdir output
if not exist "logs" mkdir logs
echo Created output and logs directories
echo.

REM Run tests
echo Running tests...
pytest tests\ -v --tb=short
if errorlevel 1 (
    echo Some tests failed (this is ok for first run^)
) else (
    echo All tests passed
)
echo.

REM Summary
echo ======================================================================
echo                     Setup Complete!
echo ======================================================================
echo.
echo Next steps:
echo.
echo 1. Test with a few parsers:
echo    python main.py --max-parsers 5 --parser-types community --verbose
echo.
echo 2. Run full conversion:
echo    python main.py
echo.
echo 3. Monitor progress:
echo    type logs\conversion.log
echo.
echo 4. Check results:
echo    type output\conversion_report.md
echo.
echo For more information, see:
echo    - README.md: Complete documentation
echo    - SETUP.md: Detailed setup guide
echo    - PROJECT_SUMMARY.md: Project overview
echo.
echo Happy converting!
echo.
pause
