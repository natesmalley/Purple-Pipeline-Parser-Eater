# 🎯 What You Actually Need to Run This

**Status**: Code is ready, but requires setup
**Time to Setup**: 15-30 minutes (depending on internet speed)

---

## 📋 Quick Checklist

Before you can run this project, you need:

- [ ] Python 3.8+ installed (you have 3.13.5 ✅)
- [ ] Dependencies installed from requirements.txt
- [ ] Anthropic API key (Claude)
- [ ] Observo.ai API key (or use mock mode)
- [ ] GitHub token (optional, for uploads)
- [ ] config.yaml file created
- [ ] Optional: Milvus for RAG features

**Current Status**: ❌ Dependencies NOT installed

---

## 🚀 MINIMAL SETUP (Get Running in 5 Minutes)

### Step 1: Install Core Dependencies (REQUIRED)

```bash
cd purple-pipeline-parser-eater

# Install ONLY the essential packages (no ML/RAG)
pip install anthropic>=0.25.0
pip install aiohttp>=3.8.0
pip install requests>=2.31.0
pip install pyyaml>=6.0
pip install structlog>=23.1.0
pip install tenacity>=8.2.0
pip install pytest>=7.4.0
pip install pytest-asyncio>=0.21.0
```

**Size**: ~50MB download
**Time**: 2-3 minutes

### Step 2: Create Config File

```bash
# Copy example
cp config.yaml.example config.yaml

# Edit with your API key
nano config.yaml  # or notepad config.yaml on Windows
```

**Minimum Required in config.yaml**:
```yaml
anthropic:
  api_key: "sk-ant-REDACTED"  # REQUIRED
  model: "claude-3-5-sonnet-20241022"

observo:
  api_key: "mock-mode"  # Use mock mode for testing
  base_url: "https://api.observo.ai/v1"

github:
  token: "mock-mode"  # Use mock mode for testing

processing:
  max_parsers: 5  # Start small for testing
  parser_types: ["community"]
```

### Step 3: Test It!

```bash
# Quick test without real deployments
python main.py --dry-run --max-parsers 1 --verbose
```

**Expected Output**:
```
╔══════════════════════════════════════════════════╗
║     Purple Pipeline Parser Eater v1.0.0          ║
╚══════════════════════════════════════════════════╝

🔍 DRY-RUN MODE: No actual deployments will occur

🚀 Starting Purple Pipeline Parser Eater conversion system
🔧 Initializing components...
✅ All components initialized successfully
[PHASE: 1: SCAN] Scanning SentinelOne parsers from GitHub
...
```

---

## 🎓 FULL SETUP (Complete with RAG Features)

### Option A: Install Everything

```bash
# Install ALL dependencies including ML/RAG
pip install -r requirements.txt
```

**Size**: 3-5GB download (includes PyTorch)
**Time**: 10-20 minutes depending on internet
**Benefit**: Full RAG features with Milvus

### Option B: Install Without Heavy ML

Create `requirements-minimal.txt`:
```txt
# Core - REQUIRED
anthropic>=0.25.0
aiohttp>=3.8.0
requests>=2.31.0
pyyaml>=6.0
structlog>=23.1.0
tenacity>=8.2.0

# Data Processing - REQUIRED
pandas>=2.0.0
jsonschema>=4.19.0

# GitHub Integration - OPTIONAL (for uploads)
PyGithub>=1.59.0
gitpython>=3.1.0

# Testing - OPTIONAL
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-mock>=3.11.0

# Utility - REQUIRED
python-dotenv>=1.0.0
click>=8.1.0
prometheus-client>=0.17.0

# SKIP THESE FOR MINIMAL:
# pymilvus>=2.3.0  # Only if you want RAG
# sentence-transformers>=2.2.2  # Only if you want RAG
# torch>=2.0.0  # Only if you want RAG
# numpy>=1.24.0  # Only if you want RAG
```

Then:
```bash
pip install -r requirements-minimal.txt
```

**Size**: ~150MB
**Time**: 3-5 minutes
**Trade-off**: No RAG features, but everything else works

---

## 🔑 Getting API Keys

### 1. Anthropic Claude API Key (REQUIRED)

**Where**: https://console.anthropic.com/

**Steps**:
1. Sign up for Anthropic account
2. Go to "API Keys" section
3. Click "Create Key"
4. Copy the key (starts with `sk-ant-`)
5. Paste into `config.yaml`

**Cost**:
- Free tier: Limited tokens
- Pay-as-you-go: ~$3-$8 per million tokens
- For 165 parsers: Estimate $5-$15 total

**Free Alternative**: Use Claude via web, manually test 1-2 parsers

---

### 2. Observo.ai API Key (OPTIONAL - Can Use Mock Mode)

**Where**: Your Observo.ai dashboard

**Steps**:
1. Log into Observo.ai platform
2. Go to Settings → API Keys
3. Generate new API key
4. Copy and paste into `config.yaml`

**Mock Mode Alternative**:
```yaml
observo:
  api_key: "mock-mode"  # System will simulate deployments
```

**When Mock Mode is Good Enough**:
- Testing the system
- Generating LUA code only
- Not ready to deploy yet
- Just want to see how it works

---

### 3. GitHub Token (OPTIONAL - Can Use Mock Mode)

**Where**: https://github.com/settings/tokens

**Steps**:
1. Go to GitHub Settings → Developer Settings → Personal Access Tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo`, `write:packages`
4. Generate and copy token
5. Paste into `config.yaml`

**Mock Mode Alternative**:
```yaml
github:
  token: "mock-mode"  # System will simulate uploads
```

**When You Need This**:
- Only when you want to upload results to GitHub
- Can skip entirely if just testing locally

---

## 📊 What Can You Do Without What?

| Feature | Anthropic Key | Observo Key | GitHub Token | Milvus/RAG |
|---------|---------------|-------------|--------------|------------|
| Scan parsers | ❌ No | ❌ No | ❌ No | ❌ No |
| Analyze parsers | ✅ **YES** | ❌ No | ❌ No | ❌ No |
| Generate LUA | ✅ **YES** | ❌ No | ❌ No | ❌ No |
| Deploy pipelines | ✅ YES | ✅ **YES** | ❌ No | ❌ No |
| Upload to GitHub | ✅ YES | 🟡 Mock | ✅ **YES** | ❌ No |
| Generate docs | ✅ YES | ❌ No | ❌ No | ❌ No |
| RAG assistance | ✅ YES | ❌ No | ❌ No | ✅ **YES** |

**Legend**:
- ✅ **Bold** = Required for this feature
- ✅ YES = Helpful but not required
- 🟡 Mock = Can use mock mode
- ❌ No = Not needed

---

## 🎯 Recommended Setup Paths

### Path 1: "Just Want to Try It" (5 minutes)

```bash
# 1. Install minimal deps
pip install anthropic aiohttp requests pyyaml structlog tenacity pytest pytest-asyncio

# 2. Create minimal config
cat > config.yaml << EOF
anthropic:
  api_key: "YOUR-CLAUDE-KEY"
  model: "claude-3-5-sonnet-20241022"
observo:
  api_key: "mock-mode"
github:
  token: "mock-mode"
processing:
  max_parsers: 2
  parser_types: ["community"]
EOF

# 3. Run in dry-run
python main.py --dry-run --max-parsers 1
```

**Result**: See how it works without deploying anything

---

### Path 2: "Generate LUA Code Only" (10 minutes)

```bash
# 1. Install deps (no RAG)
pip install anthropic aiohttp requests pyyaml structlog tenacity pandas jsonschema pytest pytest-asyncio python-dotenv click prometheus-client

# 2. Full config with mock mode
cp config.yaml.example config.yaml
# Edit: Add real Anthropic key, keep others as "mock-mode"

# 3. Run for real
python main.py --max-parsers 10 --parser-types community
```

**Result**:
- Gets real parser analysis from Claude
- Generates actual LUA code
- Saves to `output/lua_transformations/`
- Simulates deployment (doesn't actually deploy)

---

### Path 3: "Full Production Deploy" (30 minutes)

```bash
# 1. Install everything
pip install -r requirements.txt

# 2. Setup Milvus (optional, for RAG)
docker-compose up -d milvus

# 3. Get all API keys
# - Anthropic (required)
# - Observo.ai (required for deployment)
# - GitHub (required for uploads)

# 4. Full config
cp config.yaml.example config.yaml
# Edit: Add ALL real API keys

# 5. Run full conversion
python main.py
```

**Result**:
- Full conversion of all 165 parsers
- Actual deployment to Observo.ai
- Upload to GitHub repository
- Complete with RAG documentation

---

## ⚡ Quick Start Commands

### I just want to see if it works:
```bash
pip install anthropic aiohttp pyyaml
echo "anthropic:
  api_key: 'YOUR-KEY'
  model: 'claude-3-5-sonnet-20241022'
observo:
  api_key: 'mock'
github:
  token: 'mock'
processing:
  max_parsers: 1
  parser_types: ['community']" > config.yaml
python main.py --dry-run --max-parsers 1 --verbose
```

### I want to generate real LUA code:
```bash
pip install anthropic aiohttp requests pyyaml structlog tenacity pandas
cp config.yaml.example config.yaml
# Edit config.yaml - add real Anthropic key
python main.py --max-parsers 5 --parser-types community
# Check output/lua_transformations/ for generated code
```

### I want full deployment:
```bash
pip install -r requirements.txt
cp config.yaml.example config.yaml
# Edit config.yaml - add ALL real API keys
python main.py --max-parsers 10  # Test with 10 first
# If successful:
python main.py  # Full 165 parsers
```

---

## 🐛 Troubleshooting First Run

### "ModuleNotFoundError: No module named 'anthropic'"
```bash
# Solution: Install dependencies
pip install anthropic
```

### "Configuration file not found"
```bash
# Solution: Create config.yaml
cp config.yaml.example config.yaml
nano config.yaml
```

### "Anthropic API key not configured"
```bash
# Solution: Add real API key to config.yaml
# Get key from: https://console.anthropic.com/
```

### "ImportError: cannot import name 'X'"
```bash
# Solution: Install missing package
pip install <package-name>
# Or install all:
pip install -r requirements.txt
```

### "Rate limit exceeded"
```bash
# Solution: Increase delays in config.yaml
anthropic:
  rate_limit_delay: 2.0  # Increase from 1.0
```

### Out of memory with 165 parsers
```bash
# Solution: Process in smaller batches
python main.py --max-parsers 50  # Process 50 at a time
```

---

## 📝 What's Actually Required vs Optional

### REQUIRED (Won't Run Without):
1. ✅ Python 3.8+ (you have 3.13 ✅)
2. ✅ `anthropic` package
3. ✅ `aiohttp` package
4. ✅ `pyyaml` package
5. ✅ `config.yaml` file
6. ✅ Valid Anthropic API key (for analysis)

### HIGHLY RECOMMENDED (For Full Features):
7. 🟡 `requests`, `structlog`, `tenacity`, `pandas`
8. 🟡 Observo.ai API key (or use mock mode)
9. 🟡 GitHub token (or use mock mode)

### OPTIONAL (Nice to Have):
10. ⚪ Milvus + RAG dependencies (for enhanced docs)
11. ⚪ PyGithub (for advanced GitHub features)
12. ⚪ pytest (for running tests)

---

## 💰 Cost Estimate

### Free Tier Testing:
- **Anthropic**: Free tier gives you enough to test with 5-10 parsers
- **Time**: Can test in 10 minutes
- **Cost**: $0

### Small Scale (10-20 parsers):
- **Anthropic**: ~$1-$3
- **Observo.ai**: Check your plan (likely free for testing)
- **GitHub**: Free
- **Total**: $1-$3

### Full Scale (165 parsers):
- **Anthropic**: ~$5-$15 (depends on complexity)
- **Observo.ai**: Check your plan
- **GitHub**: Free
- **Total**: $5-$20

---

## ✅ Final Checklist Before Running

```bash
# Check Python version (need 3.8+)
python --version

# Check if in correct directory
pwd  # Should show: .../Purple-Pipline-Parser-Eater/purple-pipeline-parser-eater

# Install minimal deps
pip install anthropic aiohttp pyyaml structlog

# Create config
cp config.yaml.example config.yaml

# Edit config - add your Anthropic API key
# On Windows: notepad config.yaml
# On Mac/Linux: nano config.yaml

# Test import
python -c "from orchestrator import ConversionSystemOrchestrator; print('✅ Ready!')"

# Run test
python main.py --dry-run --max-parsers 1 --verbose
```

If all these work, **you're ready to run!** 🚀

---

## 🎯 TL;DR - Absolute Minimum to Get Started

```bash
# 1. Install must-have packages (2 minutes)
pip install anthropic aiohttp pyyaml

# 2. Create config with your Claude API key (1 minute)
cp config.yaml.example config.yaml
# Edit config.yaml - add Anthropic key, leave rest as "mock-mode"

# 3. Run test (30 seconds)
python main.py --dry-run --max-parsers 1

# ✅ If that works, you're good to go!
```

**That's it!** Everything else is optional enhancements.

