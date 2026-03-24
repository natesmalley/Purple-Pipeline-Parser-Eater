# RAG External Sources Guide

## Overview

The Purple Pipeline Parser Eater RAG system supports **automatic ingestion and updating** from multiple external sources:

- 🌐 **Websites** - Crawl documentation websites with configurable depth
- 🐙 **GitHub** - Fetch documentation from public/private repositories
- 🪣 **AWS S3** - Ingest documents from S3 buckets
- 📁 **Git Repositories** - Local git repository scanning

All sources support:
- ✅ **Automatic Updates** - Scheduled refresh at configurable intervals
- ✅ **Change Detection** - Only updates modified documents
- ✅ **Caching** - Reduces unnecessary network requests
- ✅ **Version Tracking** - Content hashing for diff detection

---

## Configuration

### config.yaml Structure

```yaml
# RAG External Sources Configuration
rag_sources:
  enabled: true              # Enable external sources
  auto_update: true          # Enable automatic updates
  update_interval: "24h"     # Global default update interval

  sources:
    # Define your sources here
    - type: "website|github|s3|git"
      name: "Source Name"
      enabled: true
      # ... source-specific configuration
```

### Update Intervals

Supported interval formats:
- `"1h"`, `"24h"` - Hours
- `"1d"`, `"7d"` - Days
- `"1w"` - Weeks
- `"30m"` - Minutes (for testing)

---

## Source Types

### 1. Website Scraping

Crawls documentation websites, following links up to a specified depth.

**Configuration Example:**

```yaml
- type: "website"
  name: "Observo Documentation"
  url: "https://docs.observo.ai"
  enabled: true
  depth: 3                    # Follow links up to 3 levels deep
  patterns: ["*.html", "*.md"] # File patterns to scrape
  exclude_patterns:           # Patterns to exclude
    - "**/archive/*"
    - "**/deprecated/*"
  update_interval: "24h"      # Check for updates daily
```

**Parameters:**
- `url` - Base URL to start crawling
- `depth` - Maximum link depth (0 = only base URL, 1 = base + direct links)
- `patterns` - File patterns to include (glob syntax)
- `exclude_patterns` - Patterns to skip (optional)

**Use Cases:**
- Official product documentation sites
- API reference documentation
- Internal wiki sites
- Knowledge base systems

---

### 2. GitHub Repository

Fetches documentation from GitHub repositories via the GitHub API.

**Configuration Example:**

```yaml
- type: "github"
  name: "Observo Examples"
  url: "https://github.com/observo-ai/examples"
  enabled: true
  branch: "main"              # Git branch to fetch
  paths:                      # Paths to fetch (empty = all)
    - "docs/"
    - "README.md"
    - "examples/"
  patterns: ["*.md", "*.txt"] # File patterns to include
  auth:
    token: "ghp_xxxxxxxxxxxx" # GitHub personal access token
  update_interval: "12h"      # Check for updates twice daily
```

**Parameters:**
- `url` - GitHub repository URL (https://github.com/owner/repo)
- `branch` - Git branch to fetch from (default: "main")
- `paths` - Specific paths to fetch (empty = entire repo)
- `patterns` - File patterns to include
- `auth.token` - GitHub PAT for private repos (optional for public)

**Authentication:**
- **Public Repos**: No token required
- **Private Repos**: Create GitHub Personal Access Token
  1. Go to GitHub Settings → Developer settings → Personal access tokens
  2. Generate new token with `repo` scope
  3. Add to config as `auth.token`

**Use Cases:**
- Internal documentation repositories
- Code examples and samples
- Markdown-based documentation
- README files across multiple projects

---

### 3. AWS S3 Bucket

Fetches documents from AWS S3 buckets.

**Configuration Example:**

```yaml
- type: "s3"
  name: "Internal Documentation"
  enabled: true
  bucket: "my-observo-docs"   # S3 bucket name
  prefix: "documentation/"    # Prefix/folder path
  patterns:                   # File patterns to include
    - "*.md"
    - "*.txt"
    - "*.json"
  auth:
    aws_access_key_id: "AKIAXXXXXXXXXXXXXXXX"
    aws_secret_access_key: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    region: "us-east-1"
  update_interval: "6h"       # Check for updates 4 times daily
```

**Parameters:**
- `bucket` - S3 bucket name
- `prefix` - Object key prefix (folder path)
- `patterns` - File patterns to include
- `auth.aws_access_key_id` - AWS access key
- `auth.aws_secret_access_key` - AWS secret key
- `auth.region` - AWS region

**Requirements:**
- `boto3` Python package must be installed
- AWS credentials with `s3:GetObject` and `s3:ListBucket` permissions

**Use Cases:**
- Centralized documentation storage
- Shared team documentation
- Exported reports and logs
- Cloud-based knowledge bases

---

### 4. Local Git Repository

Scans local git repositories for documentation files.

**Configuration Example:**

```yaml
- type: "git"
  name: "Local Documentation"
  enabled: true
  path: "C:/projects/observo-docs"  # Windows path
  # path: "/home/user/observo-docs" # Linux path
  patterns: ["*.md", "*.rst"]
  update_interval: "1h"       # Check for updates hourly
```

**Parameters:**
- `path` - Absolute path to git repository
- `patterns` - File patterns to include

**Use Cases:**
- Local documentation development
- Offline documentation access
- Internal git repositories
- Fast updates for frequently changing docs

---

## Usage

### Initial Ingestion

Ingest all sources (local + external):

```bash
python ingest_all_sources.py
```

**Output:**
```
🚀 PURPLE PIPELINE PARSER EATER - RAG INGESTION
   Complete Knowledge Base Population

✅ RAG knowledge base connected and ready

📚 LOCAL DOCUMENTATION INGESTION
  Total files: 15
  Chunks ingested: 247

🌐 EXTERNAL SOURCES INGESTION
  Sources processed: 3
  New documents added: 128
  Documents updated: 5

🎉 COMPLETE INGESTION FINISHED!
  Total documents in RAG: 375
```

### Local Documentation Only

Ingest only local Observo docs:

```bash
python ingest_observo_docs.py
```

### Auto-Update Service

Run background service for automatic updates:

```bash
python rag_auto_updater.py
```

**Service Features:**
- ✅ Continuous monitoring
- ✅ Scheduled updates at configured intervals
- ✅ Change detection (only updates modified docs)
- ✅ Logging to `rag_auto_updater.log`
- ✅ Graceful shutdown (Ctrl+C)

**Service Output:**
```
RAG Auto-Update Service Starting
✅ RAG knowledge base initialized
Monitoring 3 external sources
  - Observo Documentation: website (interval: 24h)
  - Observo Examples: github (interval: 12h)
  - Internal Documentation: s3 (interval: 6h)

Service started - checking for updates every 21600s
Press Ctrl+C to stop

Update Check #1 - 2025-10-08 14:30:00
  Sources processed: 3
  New documents: 0
  Updated documents: 2
  Unchanged documents: 126
Next update: 2025-10-08 20:30:00
```

---

## Advanced Features

### Caching System

All scraped content is cached locally in `rag_cache/`:
- **Reduces network requests** - Only fetches if cache expired
- **Faster restarts** - Immediate availability of cached docs
- **Configurable TTL** - Per-source `update_interval` controls cache lifetime

**Cache Structure:**
```
rag_cache/
  ├── 5d41402abc4b2a76b9719d911017c592.json  # Website cache
  ├── 7c6a180b36896a0a8c02787eeafb0e4c.json  # GitHub cache
  └── 6cb75f652a9b52798eb6cf2201057c73.json  # S3 cache
```

### Version Tracking

Content hashing detects document changes:
- **SHA-256 hashing** - Content-based change detection
- **Efficient updates** - Only modified documents are updated
- **History tracking** - Update log maintains change history

### Error Handling

Robust error handling for network issues:
- **Retry logic** - Automatic retry after failures
- **Partial failures** - Other sources continue if one fails
- **Error logging** - Comprehensive error tracking

---

## Best Practices

### 1. Update Intervals

Choose appropriate intervals based on change frequency:

| Documentation Type | Recommended Interval | Rationale |
|--------------------|---------------------|-----------|
| Official product docs | `24h` | Updated infrequently |
| API reference | `12h` | May change with releases |
| Internal wiki | `6h` | Updated frequently |
| Development repos | `1h` | Active development |

### 2. Pattern Matching

Use specific patterns to reduce noise:

**Good:**
```yaml
patterns: ["docs/**/*.md", "README.md"]
exclude_patterns: ["**/archive/*", "**/test/*"]
```

**Avoid:**
```yaml
patterns: ["*"]  # Too broad, includes irrelevant files
```

### 3. Authentication Security

Protect credentials:

**Best:**
- Store credentials in environment variables
- Use AWS IAM roles when possible
- Rotate tokens regularly

**Avoid:**
- Committing credentials to git
- Using overly permissive credentials

### 4. Monitoring

Monitor the auto-update service:

```bash
# View live logs
tail -f rag_auto_updater.log

# Check for errors
grep ERROR rag_auto_updater.log

# Monitor update frequency
grep "Update Check" rag_auto_updater.log
```

---

## Troubleshooting

### Issue: "External sources disabled in config"

**Solution:** Set `rag_sources.enabled: true` in config.yaml

### Issue: "No external sources enabled"

**Solution:** Set `enabled: true` for at least one source

### Issue: GitHub rate limiting

**Symptoms:** HTTP 403 errors from GitHub API

**Solution:**
- Add authentication token to increase rate limit
- Reduce update frequency (increase `update_interval`)

### Issue: S3 access denied

**Symptoms:** boto3 ClientError with 403 status

**Solution:**
- Verify AWS credentials are correct
- Check IAM permissions include `s3:GetObject` and `s3:ListBucket`
- Verify bucket name and region are correct

### Issue: Website scraping timeout

**Symptoms:** asyncio timeout errors

**Solution:**
- Reduce crawl `depth`
- Use more specific `patterns` to limit scope
- Check website accessibility and response time

---

## Performance Optimization

### Large Documentation Sets

For large documentation sources:

1. **Limit Crawl Depth**
   ```yaml
   depth: 2  # Instead of 3 or higher
   ```

2. **Use Specific Patterns**
   ```yaml
   patterns: ["docs/**/*.md"]  # Not "**/*"
   ```

3. **Increase Update Interval**
   ```yaml
   update_interval: "24h"  # Not "1h"
   ```

4. **Enable Caching**
   - Cache is enabled by default
   - Reduces redundant network requests

### Memory Usage

- Each document ~5-10KB in memory
- 1000 documents ≈ 5-10MB memory
- Cache files stored on disk, not in RAM

---

## Integration with Main Application

The RAG external sources integrate seamlessly:

```python
from components.rag_knowledge import RAGKnowledgeBase
from components.observo_query_patterns import ObservoQueryPatterns

# Initialize RAG (includes external sources)
rag = RAGKnowledgeBase(config)

# Query across all sources (local + external)
query_patterns = ObservoQueryPatterns(rag)
results = await query_patterns.find_source_configuration("okta")

# Results include documents from:
# - Local observo docs/
# - External websites
# - GitHub repositories
# - S3 buckets
```

---

## Example Configurations

### Observo.ai Official Documentation

```yaml
- type: "website"
  name: "Observo Official Docs"
  url: "https://docs.observo.ai"
  enabled: true
  depth: 3
  patterns: ["*.html", "*.md"]
  update_interval: "24h"
```

### GitHub Examples Repository

```yaml
- type: "github"
  name: "Observo Examples"
  url: "https://github.com/observo-ai/examples"
  enabled: true
  branch: "main"
  paths: ["docs/", "examples/"]
  patterns: ["*.md"]
  update_interval: "12h"
```

### Centralized S3 Documentation

```yaml
- type: "s3"
  name: "Team Documentation"
  enabled: true
  bucket: "company-observo-docs"
  prefix: "team-docs/"
  patterns: ["*.md", "*.txt"]
  auth:
    aws_access_key_id: "${AWS_ACCESS_KEY_ID}"
    aws_secret_access_key: "${AWS_SECRET_ACCESS_KEY}"
    region: "us-east-1"
  update_interval: "6h"
```

---

## Summary

The RAG external sources system provides:

✅ **Flexibility** - Multiple source types supported
✅ **Automation** - Auto-update with change detection
✅ **Performance** - Caching and efficient updates
✅ **Reliability** - Robust error handling
✅ **Security** - Safe credential management

**Result:** Always up-to-date knowledge base for RAG-enhanced Observo pipeline generation!

---

## Additional Resources

- [Main README](README.md)
- [RAG Knowledge Base Documentation](components/rag_knowledge.py)
- [Observo Query Patterns](components/observo_query_patterns.py)
- [Configuration Guide](SETUP.md)
