# Quick Start: GitHub Cloud Sync

**One-page guide to start RAG GitHub cloud synchronization**

---

## ✅ Prerequisites (Already Done)

- [x] Docker running
- [x] Milvus containers healthy
- [x] RAG populated (176 documents)
- [x] GitHub sync code implemented

---

## 🚀 Quick Start (3 Steps)

### 1. Verify Docker is Running

```bash
docker ps | grep milvus
```

Should show: `milvus-standalone`, `milvus-minio`, `milvus-etcd` all UP

### 2. Test Single Sync Cycle

```bash
cd purple-pipeline-parser-eater
python test_github_sync.py
```

### 3. Start Continuous Service

```bash
python start_rag_autosync_github.py
```

**Done!** Service now checks GitHub every 60 minutes.

---

## ⚙️ Configuration

Edit `config.yaml`:

```yaml
rag_auto_update:
  enabled: true           # On/off switch
  interval_minutes: 60    # How often to check

github:
  token: ""              # Optional: Add for 5000 req/hr
```

---

## 📊 Check Status

### Docker/Milvus Running?
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Documents in RAG?
```bash
python -c "from pymilvus import *; connections.connect(); print(Collection('observo_knowledge').num_entities)"
```

### View Logs
```bash
tail -f logs/rag_autosync.log
```

---

## 🔧 Common Commands

```bash
# Test sync (single cycle)
python test_github_sync.py

# Start service (continuous)
python start_rag_autosync_github.py

# Stop service
Ctrl+C

# View state
cat data/rag_sync_state.json

# Check Docker
docker ps | grep milvus
```

---

## ⚠️ Current Status

**GitHub Rate Limit:** Hit limit earlier (resets in ~1 hour)

**Options:**
1. **Wait**: Automatically works after 1 hour
2. **Add token**: Get 5000 requests/hour instead of 60

**To add token:**
1. Visit: https://github.com/settings/tokens
2. Generate token (scope: `public_repo`)
3. Add to `config.yaml`:
   ```yaml
   github:
     token: "ghp_your_token_here"
   ```

---

## 📁 Files

| File | Purpose |
|------|---------|
| `test_github_sync.py` | Test single sync cycle |
| `start_rag_autosync_github.py` | Run continuous service |
| `config.yaml` | Configuration |
| `logs/rag_autosync.log` | Service logs |
| `data/rag_sync_state.json` | Sync state |

---

## ✅ System Status

- **Docker**: All 3 containers healthy ✅
- **Milvus**: Running on localhost:19530 ✅
- **RAG**: 176 documents loaded ✅
- **Sync Code**: Tested and working ✅
- **Waiting**: GitHub rate limit reset ⏳

---

## 🎯 Next Action

**After rate limit resets** (~1 hour from last request):

```bash
cd purple-pipeline-parser-eater
python start_rag_autosync_github.py
```

Service will then:
- Check GitHub every 60 minutes
- Detect new/updated parsers
- Automatically sync to RAG
- Log all activity

**That's it! Your RAG will stay synced with GitHub automatically.**
