# 🚀 Setup Guide - Purple Pipeline Parser Eater

Complete setup instructions for getting Purple Pipeline Parser Eater running on your system.

## 📋 Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation Steps](#installation-steps)
3. [Configuration](#configuration)
4. [Optional Components](#optional-components)
5. [Verification](#verification)
6. [First Run](#first-run)

## 🖥️ System Requirements

### Minimum Requirements
- **OS**: Windows 10+, macOS 10.15+, Linux (Ubuntu 20.04+)
- **Python**: 3.8 or higher
- **Memory**: 4GB RAM
- **Storage**: 500MB free space
- **Network**: Stable internet connection

### Recommended Requirements
- **Python**: 3.10 or higher
- **Memory**: 8GB+ RAM
- **CPU**: 4+ cores
- **Storage**: 2GB+ free space

## 📦 Installation Steps

### Step 1: Install Python

#### Windows
```powershell
# Download from python.org and install
# Or use Chocolatey
choco install python --version=3.10
```

#### macOS
```bash
# Using Homebrew
brew install python@3.10
```

#### Linux
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip

# CentOS/RHEL
sudo yum install python3.10
```

### Step 2: Clone Repository

```bash
git clone https://github.com/your-org/purple-pipeline-parser-eater.git
cd purple-pipeline-parser-eater
```

### Step 3: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### Step 4: Install Dependencies

```bash
# Install all required packages
pip install -r requirements.txt

# For development (with testing tools)
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-mock pytest-cov
```

## ⚙️ Configuration

### Step 1: Create Configuration File

```bash
# Copy example configuration
cp config.yaml.example config.yaml

# Or create new file
nano config.yaml  # or use your preferred editor
```

### Step 2: Add API Keys

Edit `config.yaml` and add your API keys:

```yaml
anthropic:
  api_key: "sk-ant-..."  # Get from https://console.anthropic.com/

observo:
  api_key: "obs-..."     # Get from Observo.ai dashboard
  base_url: "https://api.observo.ai/v1"

github:
  token: "ghp_..."       # Get from https://github.com/settings/tokens
  target_repo_owner: "your-github-username"
  target_repo_name: "observo-pipelines"
```

### Step 3: Configure Processing Options

```yaml
processing:
  max_parsers: 10        # Start with a small number for testing
  parser_types: ["community"]  # Start with community parsers
  batch_size: 5
  max_concurrent: 2
```

### Getting API Keys

#### Anthropic Claude API Key
1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to API Keys section
4. Create new API key
5. Copy the key starting with `sk-ant-`

#### Observo.ai API Key
1. Log in to your Observo.ai dashboard
2. Navigate to Settings → API Keys
3. Generate new API key
4. Copy the API key

#### GitHub Token (Optional)
1. Go to https://github.com/settings/tokens
2. Generate new token (classic)
3. Select scopes: `repo`, `write:packages`
4. Copy the token

## 🔧 Optional Components

### Milvus Vector Database (for RAG features)

#### Using Docker (Recommended)

```bash
# Download Milvus standalone
wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml -O docker-compose.yml

# Start Milvus
docker-compose up -d

# Verify Milvus is running
docker-compose ps
```

#### Manual Installation

```bash
# Install Milvus dependencies
pip install pymilvus==2.3.0

# Configure in config.yaml
milvus:
  host: "localhost"
  port: "19530"
```

**Note**: RAG features are optional. System will work without Milvus but with limited contextual assistance.

### Sentence Transformers

```bash
# Install sentence transformers for embeddings
pip install sentence-transformers

# Download model (first run)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

## ✅ Verification

### Step 1: Verify Python Installation

```bash
python --version
# Should show Python 3.8 or higher
```

### Step 2: Verify Dependencies

```bash
# Check all packages installed
pip list | grep -E "anthropic|aiohttp|pymilvus|sentence-transformers"
```

### Step 3: Verify Configuration

```bash
# Check config file syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
# Should complete without errors
```

### Step 4: Run Tests

```bash
# Run test suite
pytest tests/ -v

# Expected output:
# test_orchestrator.py::test_initialization PASSED
# test_orchestrator.py::test_scan_parsers_phase PASSED
# ...
```

## 🎯 First Run

### Test Run with Limited Parsers

```bash
# Process just 5 parsers to test the system
python main.py --max-parsers 5 --parser-types community --verbose
```

### Expected Output

```
    ╔══════════════════════════════════════════════════════════════════════╗
    ║     Purple Pipeline Parser Eater v1.0.0                             ║
    ╚══════════════════════════════════════════════════════════════════════╝

    🎯 Convert SentinelOne parsers to Observo.ai pipelines with Claude AI

🚀 Starting Purple Pipeline Parser Eater conversion system
================================================================================
🔧 Initializing components...
✅ All components initialized successfully
[PHASE: 1: SCAN] Scanning SentinelOne parsers from GitHub
🔍 Scanning directory: https://api.github.com/repos/Sentinel-One/ai-siem/...
Found 148 community parsers
[PHASE: 1: SCAN] Completed - 5 parsers scanned
...
```

### Monitor Progress

```bash
# In another terminal, watch logs
tail -f logs/conversion.log

# Check output files
ls -lh output/
```

## 🐛 Troubleshooting

### Issue: Import Errors

```bash
# Solution: Reinstall dependencies
pip install --upgrade -r requirements.txt
```

### Issue: API Key Invalid

```bash
# Verify API key is correctly set
python -c "import yaml; print(yaml.safe_load(open('config.yaml'))['anthropic']['api_key'][:10])"
```

### Issue: Milvus Connection Failed

```bash
# Check Milvus is running
docker-compose ps

# Restart Milvus
docker-compose restart

# Check logs
docker-compose logs milvus
```

### Issue: Rate Limiting

```yaml
# Increase delays in config.yaml
anthropic:
  rate_limit_delay: 2.0  # Increase from 1.0

github:
  rate_limit_delay: 2.0  # Increase from 1.0
```

## 🎓 Next Steps

1. **Review Output**: Check `output/conversion_report.md` for detailed results
2. **Examine LUA**: Review generated LUA code in `output/lua_transformations/`
3. **Deploy Pipelines**: Use Observo.ai dashboard to activate pipelines
4. **Scale Up**: Increase `max_parsers` to process more parsers
5. **Customize**: Modify generation prompts for your specific needs

## 📚 Additional Resources

- [README.md](README.md) - Complete documentation
- [config.yaml](config.yaml) - Configuration reference
- [tests/](tests/) - Example test cases
- [GitHub Issues](https://github.com/your-org/purple-pipeline-parser-eater/issues) - Support

## 🆘 Getting Help

If you encounter issues:

1. Check [Troubleshooting](#troubleshooting) section above
2. Review logs in `logs/conversion.log`
3. Search [GitHub Issues](https://github.com/your-org/purple-pipeline-parser-eater/issues)
4. Create a new issue with:
   - Error message
   - Configuration (redact API keys)
   - Steps to reproduce
   - System information

---

**Happy Converting! 💜**
