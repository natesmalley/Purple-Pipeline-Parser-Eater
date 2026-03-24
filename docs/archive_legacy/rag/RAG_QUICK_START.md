# RAG Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Prerequisites
- Python 3.8+
- Docker Desktop (for Milvus)
- API keys configured in `config.yaml`

---

## Option 1: Local Documentation Only (Fastest)

```bash
# 1. Start Milvus
docker-compose up -d

# 2. Ingest local Observo docs
python ingest_observo_docs.py

# 3. Done! RAG is ready
```

**Result:** 250+ document chunks from 15 local files

---

## Option 2: Local + External Sources (Recommended)

```bash
# 1. Start Milvus
docker-compose up -d

# 2. Configure external sources (optional)
# Edit config.yaml and enable desired sources:
#   - Set rag_sources.enabled: true
#   - Set enabled: true for specific sources
#   - Add credentials (GitHub token, AWS keys, etc.)

# 3. Ingest all sources
python ingest_all_sources.py

# 4. Done! RAG is ready with auto-update support
```

**Result:** Local docs + external sources ingested with change detection

---

## Option 3: With Auto-Update Service (Full Features)

```bash
# 1. Start Milvus
docker-compose up -d

# 2. Configure external sources
# Edit config.yaml:
rag_sources:
  enabled: true
  auto_update: true
  update_interval: "24h"

# 3. Initial ingestion
python ingest_all_sources.py

# 4. Start auto-update service
python rag_auto_updater.py

# 5. Done! RAG updates automatically
```

**Result:** Self-updating knowledge base that stays current

---

## Configuration Examples

### Enable Website Scraping

```yaml
- type: "website"
  name: "Observo Documentation"
  url: "https://docs.observo.ai"
  enabled: true  # ← Set to true
  depth: 3
  patterns: ["*.html", "*.md"]
  update_interval: "24h"
```

### Enable GitHub Repository

```yaml
- type: "github"
  name: "Observo Examples"
  url: "https://github.com/observo-ai/examples"
  enabled: true  # ← Set to true
  branch: "main"
  paths: ["docs/", "README.md"]
  patterns: ["*.md"]
  auth:
    token: "ghp_xxxxxxxxxxxx"  # ← Add your GitHub token
  update_interval: "12h"
```

### Enable S3 Bucket

```yaml
- type: "s3"
  name: "Internal Documentation"
  enabled: true  # ← Set to true
  bucket: "my-docs-bucket"
  prefix: "documentation/"
  patterns: ["*.md", "*.txt"]
  auth:
    aws_access_key_id: "AKIAXXXXXXXX"  # ← Add AWS credentials
    aws_secret_access_key: "xxxxxxxx"
    region: "us-east-1"
  update_interval: "6h"
```

---

## Using RAG in Your Code

### Basic Query

```python
from components.rag_knowledge import RAGKnowledgeBase
import yaml

# Initialize
config = yaml.safe_load(open('config.yaml'))
rag = RAGKnowledgeBase(config)

# Search
results = rag.search(query="How to configure Okta source?", top_k=3)

for result in results:
    print(f"Title: {result['title']}")
    print(f"Content: {result['content'][:200]}...")
    print(f"Score: {result['score']}")
```

### Using Query Patterns

```python
from components.observo_query_patterns import ObservoQueryPatterns

# Initialize
patterns = ObservoQueryPatterns(rag)

# Find source configuration
results = await patterns.find_source_configuration("okta")

# Find Lua transform examples
results = await patterns.find_lua_transform_examples("json parsing")

# Find similar pipelines
results = await patterns.find_similar_pipeline("security logs")
```

### RAG-Enhanced Pipeline Building

```python
from components.observo_client import ObservoClient

# Initialize with RAG
observo = ObservoClient(config, rag_knowledge=rag)

# RAG automatically enhances:
# - Pipeline configurations
# - Lua code generation
# - Best practices lookup
# - Error resolution
```

---

## Verification

### Check Milvus Status

```bash
docker-compose ps

# Should show:
# milvus-standalone   running   0.0.0.0:19530->19530/tcp
```

### Check RAG Connection

```python
from components.rag_knowledge import RAGKnowledgeBase
import yaml

config = yaml.safe_load(open('config.yaml'))
rag = RAGKnowledgeBase(config)

if rag.enabled:
    print("✅ RAG connected successfully")
    print(f"Collection: {rag.collection_name}")
else:
    print("❌ RAG initialization failed")
```

### View Ingestion Logs

```bash
# Main logs
tail -f conversion.log

# Auto-update logs
tail -f rag_auto_updater.log
```

---

## Troubleshooting

### Milvus Not Starting

```bash
# Check Docker
docker ps

# Restart Milvus
docker-compose down
docker-compose up -d

# Check logs
docker-compose logs milvus-standalone
```

### RAG Initialization Failed

**Check:**
1. Milvus is running: `docker-compose ps`
2. Port 19530 is accessible: `netstat -an | grep 19530`
3. Dependencies installed: `pip install pymilvus sentence-transformers`

### External Source Errors

**GitHub:**
- Verify token is valid: `curl -H "Authorization: Bearer ghp_xxx" https://api.github.com/user`
- Check rate limits: 5000/hour with token, 60/hour without

**S3:**
- Verify credentials: `aws s3 ls s3://bucket-name --profile default`
- Check IAM permissions: `s3:GetObject`, `s3:ListBucket`

**Website:**
- Check URL accessibility: `curl -I https://docs.observo.ai`
- Reduce crawl depth if timeout

---

## Performance Tips

### Faster Ingestion

1. **Reduce crawl depth** (for websites)
   ```yaml
   depth: 2  # Instead of 3+
   ```

2. **Use specific patterns**
   ```yaml
   patterns: ["docs/**/*.md"]  # Not "**/*"
   ```

3. **Cache is your friend**
   - First run: slower (fetching)
   - Subsequent runs: faster (cached)

### Memory Optimization

- Each document ~5-10KB
- 1000 documents ≈ 5-10MB
- Cache stored on disk, not RAM

### Update Frequency

| Documentation Type | Interval | Rationale |
|--------------------|----------|-----------|
| Official docs | `24h` | Infrequent updates |
| API reference | `12h` | Release cycles |
| Internal wiki | `6h` | Frequent edits |
| Dev repos | `1h` | Active development |

---

## Next Steps

1. **Verify Setup**
   ```bash
   python ingest_observo_docs.py
   ```

2. **Enable External Sources** (optional)
   - Edit `config.yaml`
   - Set `enabled: true`
   - Add credentials

3. **Test RAG Queries**
   ```python
   from components.observo_query_patterns import ObservoQueryPatterns
   patterns = ObservoQueryPatterns(rag)
   results = await patterns.find_source_configuration("okta")
   ```

4. **Start Auto-Update** (optional)
   ```bash
   python rag_auto_updater.py
   ```

---

## Complete Documentation

- **[RAG External Sources Guide](RAG_EXTERNAL_SOURCES_GUIDE.md)** - Complete guide
- **[RAG Complete Implementation](RAG_COMPLETE_IMPLEMENTATION.md)** - Implementation summary
- **[Main README](README.md)** - Project overview
- **[Setup Guide](SETUP.md)** - Detailed setup

---

## Quick Commands Reference

```bash
# Start Milvus
docker-compose up -d

# Stop Milvus
docker-compose down

# Ingest local docs only
python ingest_observo_docs.py

# Ingest all sources
python ingest_all_sources.py

# Start auto-update service
python rag_auto_updater.py

# View logs
tail -f conversion.log
tail -f rag_auto_updater.log

# Check Milvus status
docker-compose ps

# Restart Milvus
docker-compose restart
```

---

**Questions?** See [RAG_EXTERNAL_SOURCES_GUIDE.md](RAG_EXTERNAL_SOURCES_GUIDE.md) for complete documentation.
