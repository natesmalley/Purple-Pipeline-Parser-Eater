# RAG Auto-Sync - Quick Reference Card

**One-page guide for using the RAG Auto-Sync system**

---

## Quick Start

```bash
# 1. Start Milvus (if not running)
docker-compose up -d

# 2. Verify RAG populated (should show 176 documents)
cd purple-pipeline-parser-eater
python -c "from pymilvus import connections, Collection; connections.connect(); c=Collection('observo_knowledge'); print(f'Docs: {c.num_entities}')"

# 3. Start auto-sync service
python start_rag_autosync.py
```

---

## Configuration (config.yaml)

```yaml
rag_auto_update:
  enabled: true                    # Enable/disable
  interval_minutes: 60             # How often to check
  local_repo_path: "C:/Users/.../ai-siem"  # Repo location
```

---

## Common Commands

### Check Status
```bash
cd purple-pipeline-parser-eater
python test_autosync.py
```

### Start Service (Background)
```bash
python start_rag_autosync.py
```

### Manual Update Check
```bash
# Force single update cycle
python components/rag_auto_updater.py
```

### View Logs
```bash
tail -f logs/rag_autosync.log
```

### Reset State (Force Re-Scan)
```bash
rm data/rag_sync_state.json
```

### Update Repository
```bash
cd C:\Users\hexideciml\Documents\GitHub\ai-siem
git pull origin main
```

---

## Status Checks

### Milvus Running?
```bash
docker ps | grep milvus
# Should show: milvus-standalone (healthy)
```

### RAG Document Count?
```bash
python -c "from pymilvus import *; connections.connect(); print(Collection('observo_knowledge').num_entities)"
```

### Auto-Sync Enabled?
```bash
python test_autosync.py
# Look for: "Enabled: True"
```

### Last Update Time?
```bash
cat data/rag_sync_state.json | grep last_update
```

---

## Configuration Examples

### Check Every 30 Minutes
```yaml
interval_minutes: 30
```

### Check Every 6 Hours
```yaml
interval_minutes: 360
```

### Disable Auto-Sync
```yaml
enabled: false
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Service won't start | Check repo path exists, Milvus running |
| No updates detected | Normal if repo unchanged. Try `git pull` |
| High CPU usage | Increase `interval_minutes` |
| State file missing | Will be created on first run |

---

## File Locations

| File | Location |
|------|----------|
| **Config** | `config.yaml` |
| **Service** | `purple-pipeline-parser-eater/start_rag_autosync.py` |
| **Logs** | `purple-pipeline-parser-eater/logs/rag_autosync.log` |
| **State** | `purple-pipeline-parser-eater/data/rag_sync_state.json` |
| **Repo** | `C:/Users/hexideciml/Documents/GitHub/ai-siem` |

---

## Current Setup

✅ **Documents in RAG:** 176
✅ **Auto-Sync:** Enabled (60 min interval)
✅ **Repository:** C:/Users/hexideciml/Documents/GitHub/ai-siem
✅ **Status:** Production Ready

---

## Next Steps

1. **Start service:** `python start_rag_autosync.py`
2. **Automate git pull:** Windows Task Scheduler (every hour)
3. **Monitor logs:** `tail -f logs/rag_autosync.log`

---

**For detailed documentation, see `RAG_AUTO_SYNC_GUIDE.md`**
