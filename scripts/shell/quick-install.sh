#!/bin/bash
# Ultra-Quick Install Script for Mac/Linux
# Gets you running in under 5 minutes

set -e

echo "======================================================================"
echo "  Purple Pipeline Parser Eater - Ultra-Quick Setup"
echo "======================================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found"
    echo "Please install Python 3.8+ from python.org"
    exit 1
fi

echo "[1/5] Installing CORE packages (anthropic, aiohttp, pyyaml)..."
pip3 install anthropic aiohttp pyyaml structlog --quiet || {
    echo "ERROR: Package installation failed"
    echo "Try: pip3 install --user anthropic aiohttp pyyaml structlog"
    exit 1
}
echo "      Done!"
echo ""

echo "[2/5] Creating config.yaml from example..."
if [ ! -f config.yaml ]; then
    cp config.yaml.example config.yaml
    echo "      Created config.yaml"
else
    echo "      config.yaml already exists"
fi
echo ""

echo "[3/5] Creating output directories..."
mkdir -p output logs
echo "      Done!"
echo ""

echo "[4/5] Testing imports..."
if ! python3 -c "from orchestrator import ConversionSystemOrchestrator" 2>/dev/null; then
    echo "      WARNING: Some imports failed"
    echo "      Installing additional packages..."
    pip3 install tenacity pandas jsonschema python-dotenv click prometheus-client --quiet
fi
echo "      Done!"
echo ""

echo "[5/5] Final check..."
python3 -c "import anthropic, aiohttp, yaml; print('  All core packages ready!')"
echo ""

echo "======================================================================"
echo "  Setup Complete!"
echo "======================================================================"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Get your Anthropic API key from: https://console.anthropic.com/"
echo ""
echo "2. Edit config.yaml and add your API key:"
echo "   nano config.yaml"
echo ""
echo "   Change this line:"
echo "     api_key: \"your-anthropic-api-key-here\""
echo "   To your actual key:"
echo "     api_key: \"sk-ant-YOUR-ACTUAL-KEY\""
echo ""
echo "3. Test with dry-run (no API calls):"
echo "   python3 main.py --dry-run --max-parsers 1 --verbose"
echo ""
echo "4. Run for real (needs API key):"
echo "   python3 main.py --max-parsers 5 --parser-types community"
echo ""
echo "For help: See README.md and WHAT_YOU_ACTUALLY_NEED.md"
echo ""
