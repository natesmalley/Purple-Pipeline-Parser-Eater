# 🧠 RAG/Milvus Setup Guide - Purple Pipeline Parser Eater

**Do You Need This?** Let's find out first!

---

## 🤔 Do I Actually Need RAG/Milvus?

### ❌ **You DON'T Need It If:**
- Just testing the system
- Generating LUA code only
- Want quick results
- Limited disk space (<5GB free)
- Just learning how it works
- Processing fewer than 50 parsers

### ✅ **You DO Need It If:**
- Want AI-enhanced documentation
- Need contextual help for troubleshooting
- Want RAG-powered optimization suggestions
- Processing large batches (100+ parsers)
- Need best practices recommendations
- Want the "full experience"

---

## 📊 What RAG Actually Does

| Feature | Without RAG | With RAG |
|---------|-------------|----------|
| Parser analysis | ✅ Works | ✅ Works |
| LUA code generation | ✅ Works | ✅ Enhanced |
| Basic documentation | ✅ Works | ✅ Enhanced |
| Deployment | ✅ Works | ✅ Works |
| **Contextual assistance** | ❌ No | ✅ **YES** |
| **Optimization tips** | ❌ Basic | ✅ **Advanced** |
| **Troubleshooting guides** | ❌ No | ✅ **YES** |
| **Best practices** | ❌ No | ✅ **YES** |

**Bottom Line**: System works fine without it. RAG adds extra intelligence.

---

## ⚖️ Cost/Benefit Analysis

### Without RAG:
- **Install time**: 5 minutes
- **Disk space**: ~150MB
- **Memory**: ~1GB
- **Features**: 90% of functionality

### With RAG:
- **Install time**: 15-30 minutes
- **Disk space**: ~5GB (PyTorch is huge)
- **Memory**: ~3-4GB
- **Features**: 100% of functionality

**Recommendation**: Start without RAG, add later if you want the extra features.

---

## 🚀 Setup Options

### **Option 1: Skip RAG Entirely (EASIEST)**

**What**: Use the system without RAG features

**How**:
```bash
# Install minimal dependencies (no RAG)
pip install -r requirements-minimal.txt

# System will automatically detect RAG is unavailable
# and disable those features gracefully
```

**Result**:
```
⚠️  RAG Knowledge Base disabled: dependencies not installed
✅ All other components initialized successfully
```

**Recommendation**: Start here!

---

### **Option 2: Install RAG with Docker (RECOMMENDED if you want RAG)**

**What**: Use Docker to run Milvus vector database

**Prerequisites**:
- Docker Desktop installed
- 5GB free disk space
- 4GB+ RAM available

**Steps**:

#### 1. Install Docker (if not already installed)

**Windows**:
- Download: https://www.docker.com/products/docker-desktop
- Install and restart
- Verify: `docker --version`

**Mac**:
```bash
brew install --cask docker
# Or download from docker.com
```

**Linux**:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

#### 2. Install Python ML Packages

```bash
# This is the big one (3-5GB download)
pip install pymilvus sentence-transformers torch numpy
```

**Time**: 10-20 minutes depending on internet

**Or install everything**:
```bash
pip install -r requirements.txt
```

#### 3. Start Milvus with Docker Compose

```bash
cd purple-pipeline-parser-eater

# Start just Milvus (not the app)
docker-compose up -d milvus etcd minio

# Wait 30 seconds for it to start
sleep 30

# Check it's running
docker-compose ps
```

**Expected Output**:
```
NAME                COMMAND                  STATUS              PORTS
milvus-standalone   "/tini -- milvus run…"   Up 30 seconds       0.0.0.0:19530->19530/tcp
milvus-etcd         "etcd -advertise-cli…"   Up 30 seconds       2379-2380/tcp
milvus-minio        "/usr/bin/docker-ent…"   Up 30 seconds       0.0.0.0:9000-9001->9000-9001/tcp
```

#### 4. Verify Milvus is Working

```bash
# Test connection
python -c "from pymilvus import connections; connections.connect('default', host='localhost', port='19530'); print('✅ Milvus connected!')"
```

#### 5. Run the Application

```bash
python main.py --dry-run --max-parsers 1 --verbose
```

**Expected in logs**:
```
✅ RAG Knowledge Base initialized successfully
📚 Ingesting Observo.ai documentation into knowledge base
✅ Ingested 10 documentation items
```

**Done!** RAG features are now active.

---

### **Option 3: Install RAG Standalone (ADVANCED)**

**What**: Install Milvus without Docker

**When**: You can't use Docker or need custom setup

**Steps**:

#### 1. Install Milvus Standalone

**Linux/Mac**:
```bash
# Download Milvus binary
wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-linux.tar.gz
tar -xvf milvus-standalone-linux.tar.gz
cd milvus-standalone

# Start Milvus
./milvus run standalone
```

**Windows**: Docker is strongly recommended. Standalone on Windows is complex.

#### 2. Install Python Packages

```bash
pip install pymilvus sentence-transformers torch numpy
```

#### 3. Configure Connection

In `config.yaml`:
```yaml
milvus:
  host: "localhost"
  port: "19530"
  collection_name: "observo_knowledge"
```

#### 4. Test

```bash
python main.py --dry-run --max-parsers 1 --verbose
```

---

## 🔧 Detailed Setup Steps (Docker Method)

### Step-by-Step with Explanations

#### **Step 1: Verify Docker is Installed**

```bash
# Check Docker
docker --version
# Should show: Docker version 20.x or higher

# Check Docker Compose
docker-compose --version
# Should show: Docker Compose version 2.x or higher
```

**Troubleshooting**:
```bash
# If Docker not found (Windows):
# - Download from docker.com/products/docker-desktop
# - Install and restart computer

# If Docker not found (Mac):
brew install --cask docker

# If Docker not found (Linux):
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

---

#### **Step 2: Install ML Python Packages**

```bash
# Navigate to project directory
cd purple-pipeline-parser-eater

# Option A: Install just RAG packages (3-5GB)
pip install pymilvus>=2.3.0
pip install sentence-transformers>=2.2.2
pip install torch>=2.0.0
pip install numpy>=1.24.0

# Option B: Install everything (includes RAG)
pip install -r requirements.txt
```

**What Each Package Does**:
- **pymilvus**: Client library for Milvus vector database
- **sentence-transformers**: Converts text to vector embeddings
- **torch**: PyTorch machine learning framework (huge!)
- **numpy**: Numerical computing library

**Expected Output**:
```
Collecting pymilvus>=2.3.0
  Downloading pymilvus-2.3.0...
[... lots of downloading ...]
Successfully installed pymilvus-2.3.0 sentence-transformers-2.2.2 torch-2.0.1 numpy-1.24.3
```

**Time**: 10-20 minutes (PyTorch is 2-3GB)

---

#### **Step 3: Start Milvus Services**

```bash
# Start Milvus and its dependencies
docker-compose up -d milvus

# This starts 3 containers:
# - milvus (the vector database)
# - etcd (metadata store)
# - minio (object storage)
```

**What Happens**:
```
Creating network "purple-pipeline-parser-eater_parser-network"
Creating volume "purple-pipeline-parser-eater_milvus-data"
Creating volume "purple-pipeline-parser-eater_etcd-data"
Creating volume "purple-pipeline-parser-eater_minio-data"
Creating milvus-etcd ... done
Creating milvus-minio ... done
Creating milvus-standalone ... done
```

**Verification**:
```bash
# Check containers are running
docker-compose ps

# Should show 3 containers with status "Up"
```

**Troubleshooting**:
```bash
# If containers fail to start, check logs:
docker-compose logs milvus

# If port conflict (19530 already in use):
# Edit docker-compose.yml and change:
#   - "19530:19530"  to  - "19531:19530"
# Then update config.yaml:
#   port: "19531"
```

---

#### **Step 4: Test Milvus Connection**

```bash
# Quick connection test
python -c "
from pymilvus import connections
connections.connect('default', host='localhost', port='19530')
print('✅ Milvus is running and accessible!')
connections.disconnect('default')
"
```

**Expected**: `✅ Milvus is running and accessible!`

**If Error**: "cannot connect to Milvus server"
```bash
# Check Milvus is actually running
docker-compose ps milvus

# Check logs for errors
docker-compose logs milvus

# Try restarting
docker-compose restart milvus
sleep 30  # Wait for startup
```

---

#### **Step 5: Run Application with RAG**

```bash
# Test with verbose output to see RAG initialization
python main.py --dry-run --max-parsers 1 --verbose
```

**Expected in Output**:
```
🔧 Initializing components...
Connected to Milvus at localhost:19530
Created and indexed collection: observo_knowledge
Loaded embedding model: all-MiniLM-L6-v2
📚 Ingesting Observo.ai documentation into knowledge base
✅ Ingested 10 documentation items
✅ RAG Knowledge Base initialized successfully
✅ All components initialized successfully
```

**If You See This**: RAG is working! 🎉

**If You See**: "RAG Knowledge Base disabled"
- Check packages installed: `pip list | grep -E "pymilvus|sentence|torch"`
- Check Milvus running: `docker-compose ps milvus`
- Check connection: Run Step 4 test again

---

## 🧪 Testing RAG Features

### Test 1: Verify RAG is Active

```python
# test_rag.py
from components.rag_knowledge import RAGKnowledgeBase
import yaml

with open('config.yaml') as f:
    config = yaml.safe_load(f)

rag = RAGKnowledgeBase(config)
print(f"RAG Enabled: {rag.enabled}")

if rag.enabled:
    # Test ingestion
    rag.ingest_observo_documentation()

    # Test search
    results = rag.search_knowledge("LUA performance optimization", top_k=3)
    print(f"Found {len(results)} relevant documents")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['title']} (score: {result['similarity_score']:.2f})")
```

**Run**:
```bash
python test_rag.py
```

**Expected Output**:
```
RAG Enabled: True
✅ Ingested 10 documentation items
Found 3 relevant documents
1. LUA Performance Optimization in Observo.ai (score: 0.95)
2. High-Volume Processing Patterns (score: 0.87)
3. Memory Management in LUA Transformations (score: 0.82)
```

### Test 2: Use RAG During Conversion

```bash
# Run a small conversion to see RAG in action
python main.py --max-parsers 5 --parser-types community --verbose

# Look for these in output:
# - "Using existing collection: observo_knowledge"
# - "Found X relevant documents for query"
# - RAG-enhanced documentation generation
```

---

## 📊 Resource Usage

### Disk Space:
- **Milvus Docker images**: ~1GB
- **Python ML packages**: ~3-4GB
- **Milvus data**: ~100-500MB (grows with usage)
- **Total**: ~5GB

### Memory:
- **Milvus running**: ~500MB-1GB
- **Sentence transformers model**: ~400MB
- **During processing**: +2-3GB
- **Total**: 3-4GB RAM recommended

### CPU:
- **Milvus**: Low usage when idle
- **Embedding generation**: Medium (during doc ingestion)
- **Vector search**: Low (very fast)

---

## 🛠️ Management Commands

### Start Milvus:
```bash
docker-compose up -d milvus
```

### Stop Milvus:
```bash
docker-compose down
```

### Restart Milvus:
```bash
docker-compose restart milvus
```

### View Logs:
```bash
docker-compose logs -f milvus
```

### Check Status:
```bash
docker-compose ps
```

### Remove Everything (clean slate):
```bash
docker-compose down -v  # -v removes volumes too
```

### Access Milvus CLI:
```bash
docker exec -it milvus-standalone milvus-cli
```

---

## 🐛 Troubleshooting

### Issue: "RAG Knowledge Base disabled: dependencies not installed"

**Cause**: Python packages not installed

**Fix**:
```bash
pip install pymilvus sentence-transformers torch numpy
```

---

### Issue: "Failed to connect to Milvus"

**Cause**: Milvus not running or wrong port

**Fix**:
```bash
# Check Milvus is running
docker-compose ps milvus

# Check port in config.yaml matches
grep -A 2 "milvus:" config.yaml

# Restart Milvus
docker-compose restart milvus
sleep 30
```

---

### Issue: "Port 19530 already in use"

**Cause**: Another service using that port

**Fix**:
```bash
# Option 1: Stop the other service
lsof -ti:19530 | xargs kill -9  # Mac/Linux
netstat -ano | findstr :19530  # Windows - note PID, then kill in Task Manager

# Option 2: Use different port
# Edit docker-compose.yml:
#   ports: ["19531:19530"]
# Edit config.yaml:
#   port: "19531"
```

---

### Issue: Slow Embedding Generation

**Cause**: CPU-only PyTorch (no GPU)

**Status**: This is normal! First run takes 2-3 minutes to download embedding model.

**Fix**: Wait for model download, subsequent runs are fast.

**To speed up with GPU**:
```bash
# Install CUDA-enabled PyTorch (if you have NVIDIA GPU)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

---

### Issue: Out of Memory

**Cause**: Not enough RAM for ML models

**Fix**:
```bash
# Option 1: Increase Docker memory limit
# Docker Desktop → Settings → Resources → Memory → Increase to 8GB

# Option 2: Close other applications

# Option 3: Process fewer parsers at once
python main.py --max-parsers 10  # Instead of 165
```

---

## 📝 Configuration Reference

### Minimal Config (No RAG):
```yaml
# config.yaml - RAG sections can be omitted
anthropic:
  api_key: "your-key"
observo:
  api_key: "mock-mode"
processing:
  max_parsers: 10
```

### Full Config (With RAG):
```yaml
# config.yaml - RAG enabled
anthropic:
  api_key: "your-key"
observo:
  api_key: "your-key"

milvus:
  host: "localhost"
  port: "19530"
  collection_name: "observo_knowledge"

processing:
  max_parsers: 165
```

---

## ✅ RAG Setup Checklist

Before running with RAG:

- [ ] Docker installed and running
- [ ] `docker-compose ps` shows 3 containers up
- [ ] Python packages installed: `pip list | grep -E "pymilvus|sentence|torch"`
- [ ] Milvus connectable: `python -c "from pymilvus import connections; connections.connect('default', 'localhost', '19530')"`
- [ ] Config has milvus section
- [ ] Test run: `python main.py --dry-run --max-parsers 1 --verbose`
- [ ] See "RAG Knowledge Base initialized successfully" in output

**All checked?** RAG is ready! 🎉

---

## 🎯 Quick Decision Guide

**Choose Your Path:**

### Path 1: "I just want it to work" → Skip RAG
```bash
pip install -r requirements-minimal.txt
python main.py --dry-run --max-parsers 5
# ✅ Works perfectly, 90% of features
```

### Path 2: "I want the full experience" → Use RAG with Docker
```bash
pip install -r requirements.txt
docker-compose up -d milvus
python main.py --dry-run --max-parsers 5 --verbose
# ✅ 100% of features, RAG-enhanced
```

### Path 3: "I'll add RAG later" → Start without, upgrade later
```bash
# Now: Skip RAG
pip install -r requirements-minimal.txt
python main.py

# Later: Add RAG when needed
pip install pymilvus sentence-transformers torch
docker-compose up -d milvus
python main.py  # RAG automatically detected and enabled
```

---

## 💡 Pro Tips

1. **First time?** Skip RAG, add it later if you want
2. **Docker issues?** Try standalone minimal install first
3. **Slow internet?** PyTorch download is huge, do it overnight
4. **Limited space?** RAG is optional, system works great without it
5. **Testing?** Use dry-run mode, RAG works in dry-run too

---

## 📞 Still Stuck?

1. **Can't install Docker?** → Use requirements-minimal.txt instead
2. **Can't download PyTorch?** → System works without RAG
3. **Connection errors?** → Check firewall/ports
4. **Still issues?** → Create an issue with logs from `docker-compose logs milvus`

**Remember**: RAG is a nice-to-have, not a must-have. The system is production-ready without it!

