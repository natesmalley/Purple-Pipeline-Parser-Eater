#!/bin/bash
# ============================================================================
# Purple Pipeline Parser Eater - Quick Start Script
# ============================================================================

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                                                                      ║"
echo "║          Purple Pipeline Parser Eater - Quick Start                 ║"
echo "║                                                                      ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Check Python version
echo "🔍 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python $required_version or higher required. Found: $python_version"
    exit 1
fi
echo "✅ Python $python_version found"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Install dependencies
echo "📚 Installing dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Check if config.yaml exists
if [ ! -f "config.yaml" ]; then
    echo "⚙️  Creating config.yaml from example..."
    if [ -f "config.yaml.example" ]; then
        cp config.yaml.example config.yaml
        echo "✅ config.yaml created"
        echo ""
        echo "⚠️  IMPORTANT: Edit config.yaml and add your API keys:"
        echo "   - Anthropic API key (Claude)"
        echo "   - Observo.ai API key"
        echo "   - GitHub token (optional)"
        echo ""
        read -p "Press Enter to open config.yaml in editor..."
        ${EDITOR:-nano} config.yaml
    else
        echo "❌ config.yaml.example not found"
        exit 1
    fi
else
    echo "✅ config.yaml already exists"
fi
echo ""

# Verify configuration
echo "🔍 Verifying configuration..."
if python3 -c "import yaml; yaml.safe_load(open('config.yaml'))" 2>/dev/null; then
    echo "✅ Configuration file is valid"
else
    echo "❌ Configuration file has syntax errors"
    exit 1
fi
echo ""

# Check API keys
echo "🔑 Checking API keys..."
anthropic_key=$(python3 -c "import yaml; print(yaml.safe_load(open('config.yaml'))['anthropic']['api_key'])" 2>/dev/null)
observo_key=$(python3 -c "import yaml; print(yaml.safe_load(open('config.yaml'))['observo']['api_key'])" 2>/dev/null)

if [ "$anthropic_key" = "your-anthropic-api-key-here" ]; then
    echo "⚠️  Anthropic API key not configured"
    echo "   Get your key from: https://console.anthropic.com/"
else
    echo "✅ Anthropic API key configured"
fi

if [ "$observo_key" = "your-observo-api-key-here" ]; then
    echo "⚠️  Observo.ai API key not configured - will run in mock mode"
    echo "   Get your key from: Observo.ai dashboard"
else
    echo "✅ Observo.ai API key configured"
fi
echo ""

# Run tests
echo "🧪 Running tests..."
if pytest tests/ -v --tb=short; then
    echo "✅ All tests passed"
else
    echo "⚠️  Some tests failed (this is ok for first run)"
fi
echo ""

# Create output directory
mkdir -p output logs
echo "✅ Created output and logs directories"
echo ""

# Summary
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                     Setup Complete! 🎉                               ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "1. Test with a few parsers:"
echo "   python3 main.py --max-parsers 5 --parser-types community --verbose"
echo ""
echo "2. Run full conversion:"
echo "   python3 main.py"
echo ""
echo "3. Monitor progress:"
echo "   tail -f logs/conversion.log"
echo ""
echo "4. Check results:"
echo "   cat output/conversion_report.md"
echo ""
echo "For more information, see:"
echo "   - README.md: Complete documentation"
echo "   - SETUP.md: Detailed setup guide"
echo "   - PROJECT_SUMMARY.md: Project overview"
echo ""
echo "Happy converting! 💜"
