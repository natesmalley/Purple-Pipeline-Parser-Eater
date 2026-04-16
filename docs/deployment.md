# Deployment Guide

Production deployment and operational reference for Purple Pipeline Parser Eater 2.

---

## Table of Contents

- [Docker Compose Setup](#docker-compose-setup)
- [Environment Variables](#environment-variables)
- [Volume Mounts and Persistence](#volume-mounts-and-persistence)
- [Production Hardening](#production-hardening)
- [Nginx Auth Proxy](#nginx-auth-proxy)
- [Monitoring and Health Checks](#monitoring-and-health-checks)
- [Scaling Considerations](#scaling-considerations)
- [Backup and Restore](#backup-and-restore)

---

## Docker Compose Setup

### Standard deployment (no RAG)

```bash
# 1. Clone the repo
git clone https://github.com/your-org/Purple-Pipeline-Parser-Eater-2.git
cd Purple-Pipeline-Parser-Eater-2

# 2. Create environment file
cp .env.example .env

# 3. Generate required secrets
echo "FLASK_SECRET_KEY=$(openssl rand -hex 32)" >> .env
echo "WEB_UI_AUTH_TOKEN=$(openssl rand -hex 32)" >> .env

# 4. Set at least one LLM provider key
# Edit .env and set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY

# 5. Start services
docker compose --env-file .env up -d

# 6. Verify health
docker compose ps
curl -f http://localhost:8080/health
```

This starts two containers:

| Container | Purpose | Port |
| --------- | ------- | ---- |
| `purple-parser-eater` | Web UI + API (gunicorn) | 8080 |
| `purple-parser-eater-worker` | Conversion worker (no ports) | -- |

### RAG deployment (with Milvus)

Adds vector-based retrieval of prior corrections for prompt enrichment.

```bash
# Set MinIO credentials (required for Milvus object storage)
echo "MINIO_ACCESS_KEY=minioadmin" >> .env
echo "MINIO_SECRET_KEY=$(openssl rand -hex 32)" >> .env

# Start with RAG profile
docker compose --env-file .env --profile rag up -d
```

Additional containers:

| Container | Purpose | Port |
| --------- | ------- | ---- |
| `purple-milvus` | Vector database | 19530, 9091 |
| `purple-etcd` | Milvus metadata store | 2379 (internal) |
| `purple-minio` | Milvus object storage | 9000 (internal) |

---

## Environment Variables

### Required

| Variable | Description | How to generate |
| -------- | ----------- | --------------- |
| `FLASK_SECRET_KEY` | Flask session signing key. Fail-fast if missing. | `openssl rand -hex 32` |
| `WEB_UI_AUTH_TOKEN` | Bearer token for API auth. Required when binding to non-loopback. | `openssl rand -hex 32` |

At least one LLM provider key is required:

| Variable | Description |
| -------- | ----------- |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `GEMINI_API_KEY` | Google Gemini API key |

### LLM configuration

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `LLM_PROVIDER_PREFERENCE` | `anthropic` | Active provider: `anthropic`, `openai`, or `gemini` |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Standard (cheap) Anthropic model |
| `ANTHROPIC_STRONG_MODEL` | `claude-sonnet-4-6` | Strong (escalation) Anthropic model |
| `OPENAI_MODEL` | `gpt-5.4-mini` | Standard OpenAI model |
| `OPENAI_STRONG_MODEL` | `gpt-5.4` | Strong OpenAI model |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Standard Gemini model |
| `GEMINI_STRONG_MODEL` | `gemini-3.1-pro` | Strong Gemini model |
| `LLM_MAX_TOKENS` | `3000` | Maximum tokens per LLM response |
| `LLM_MAX_ITERATIONS` | `2` | Harness feedback iterations before escalation |
| `LLM_TEMPERATURE` | `0` | Temperature (pinned to 0, do not change) |

### Application

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `APP_ENV` | `production` | Environment identifier |
| `LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |
| `WEB_UI_HOST` | `0.0.0.0` | Web server bind address |
| `WEB_UI_PORT` | `8080` | Web server port |
| `WEB_UI_TLS_TERMINATED_UPSTREAM` | `1` | Set to 1 when behind a TLS-terminating proxy |
| `GUNICORN_WORKERS` | `1` | Number of gunicorn worker processes |
| `WORKBENCH_MAX_SAMPLE_CHARS` | `150000` | Per-sample character limit |
| `WORKBENCH_MAX_TOTAL_SAMPLE_CHARS` | `1500000` | Total character limit across all samples |

### Integrations

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `GITHUB_TOKEN` | -- | GitHub personal access token (scopes: `repo`, `write:packages`) |
| `MILVUS_HOST` | `milvus` | Milvus hostname (Docker service name) |
| `MILVUS_PORT` | `19530` | Milvus gRPC port |

### IPC paths (usually no need to change)

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `STATE_STORE_PATH` | `/app/data/state/pending_state.json` | StateStore file |
| `FEEDBACK_CHANNEL_PATH` | `/app/data/feedback/actions.jsonl` | FeedbackChannel file |
| `FEEDBACK_DRAIN_OFFSET_PATH` | `/app/data/feedback/drain_offset.json` | Worker drain offset |
| `RUNTIME_SNAPSHOT_PATH` | `/app/data/runtime/status_snapshot.json` | Runtime status snapshot |
| `RUNTIME_PENDING_REQUESTS_PATH` | `/app/data/runtime/pending_requests.json` | Pending requests file |

### Docker image selection

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `PPPE_IMAGE` | `ghcr.io/natesmalley/purple-pipeline-parser-eater` | Container image |
| `PPPE_TAG` | `latest` | Image tag |
| `PPPE_CONFIG_FILE` | `./config.yaml.example` | Config file bind mount source |

### RAG profile (Milvus)

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO root user |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO root password (change in production) |

---

## Volume Mounts and Persistence

### Named volumes

| Volume | Container mount | Data |
| ------ | --------------- | ---- |
| `app-data` | `/app/data` | IPC state, feedback JSONL, settings, runtime snapshots. Shared by both containers. |
| `app-output` | `/app/output` | Accepted Lua scripts, harness reports. Shared by both containers. |
| `app-logs` | `/app/logs` | Application log files |
| `milvus-data` | `/var/lib/milvus` | Milvus vector data (RAG profile) |
| `etcd-data` | `/etcd` | etcd key-value data (RAG profile) |
| `minio-data` | `/minio_data` | MinIO object storage (RAG profile) |

### tmpfs mounts

The containers use a read-only root filesystem. Writable directories are tmpfs:

| Mount | Size | Purpose |
| ----- | ---- | ------- |
| `/tmp` | 4 GB | Python temp files, torch cache |
| `/home/appuser/.cache` | 2 GB | Sentence-transformers model cache |
| `/var/tmp` | 1 GB | Additional temp files |

### Config file mount

The config file is bind-mounted read-only:

```yaml
volumes:
  - type: bind
    source: ${PPPE_CONFIG_FILE:-./config.yaml.example}
    target: /app/config.yaml
    read_only: true
```

To use a custom config, set `PPPE_CONFIG_FILE=./config.yaml` in your `.env` and create the file.

---

## Production Hardening

### FLASK_SECRET_KEY

**Fail-fast**: the web worker refuses to start without this set. Generate with `openssl rand -hex 32`.

This key signs Flask sessions. Use a unique, random value. Rotating it invalidates all active sessions.

### WEB_UI_AUTH_TOKEN

**Required when `WEB_UI_HOST` is not loopback** (i.e., always in Docker). Every API request must include this as the `X-Auth-Token` header.

Generate with `openssl rand -hex 32`. Treat this as a shared secret between the operator's browser/tools and the server.

### Read-only root filesystem

Enabled by default (`read_only: true` in `docker-compose.yml`). All writable paths use tmpfs or named volumes.

### Capability restrictions

```yaml
cap_drop:
  - ALL
security_opt:
  - no-new-privileges:true
```

No capabilities are added back. The container runs as UID/GID 999 (non-root).

### Resource limits

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 16G
    reservations:
      cpus: '2'
      memory: 8G
```

Adjust based on your workload. The 16 GB limit accounts for sentence-transformers model loading when RAG is enabled.

### Supply-chain and secret scanning

Two CI gates are provided:

- `scripts/run_pip_audit.sh` -- scans `requirements.txt` for known vulnerabilities
- `scripts/run_gitleaks.sh` -- scans for leaked secrets in the repository

Run both locally before pushing changes.

### DEBUG mode

`DEBUG=False` is enforced in the production Flask app. Do not override.

---

## Nginx Auth Proxy

For production deployments, place nginx in front of the web worker to handle TLS termination and additional access control.

### Example nginx configuration

```nginx
server {
    listen 443 ssl;
    server_name pppe.example.com;

    ssl_certificate     /etc/ssl/certs/pppe.crt;
    ssl_certificate_key /etc/ssl/private/pppe.key;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # Forward auth token
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Pass through the auth token
        proxy_set_header X-Auth-Token $http_x_auth_token;

        # Timeouts for long-running LLM requests
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

Set `WEB_UI_TLS_TERMINATED_UPSTREAM=1` in the container environment when using a TLS-terminating proxy.

---

## Monitoring and Health Checks

### Docker health check

The web worker exposes `GET /health` for Docker's built-in health check:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 120s
```

The 120-second start period accounts for model loading when RAG is enabled.

### Prometheus metrics

`GET /api/v1/metrics` exposes Prometheus-format metrics including conversion counts, harness scores, and error rates.

### Log monitoring

Both containers use JSON-file logging with rotation:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "100m"
    max-file: "5"
    compress: "true"
```

View logs:

```bash
# Web worker
docker compose logs -f parser-eater

# Conversion worker
docker compose logs -f parser-eater-worker

# Both
docker compose logs -f
```

### Checking service status

```bash
# Container status
docker compose ps

# Health check status
docker inspect --format='{{.State.Health.Status}}' purple-parser-eater

# Runtime status via API
curl -H "X-Auth-Token: $WEB_UI_AUTH_TOKEN" http://localhost:8080/api/v1/status
```

---

## Scaling Considerations

### Gunicorn workers

The default is 1 gunicorn worker (`GUNICORN_WORKERS=1`). This is intentional -- the StateStore follower uses mtime-based hot-reload and is designed for single-worker operation. Increasing workers can cause state synchronization issues.

### Conversion worker

The conversion worker is single-instance by design. It processes parsers sequentially and coordinates with the web worker through file IPC. Do not run multiple conversion worker containers against the same `app-data` volume.

### Milvus scaling

Milvus runs in standalone mode in this deployment. For high-volume RAG workloads, consider:

- Increasing Milvus memory limits
- Using a dedicated etcd cluster
- Switching to Milvus cluster mode (requires a separate deployment topology)

### CPU and memory

- Without RAG: 2 CPU / 4 GB memory is sufficient for most workloads
- With RAG: 2 CPU / 8-16 GB memory (sentence-transformers model loading is memory-intensive)
- LLM calls are network-bound, not CPU-bound

---

## Backup and Restore

### What to back up

| Path | Contents | Priority |
| ---- | -------- | -------- |
| `app-data` volume | Settings, feedback, state, corrections | Critical |
| `app-output` volume | Accepted Lua scripts, reports | Important |
| `.env` | Secrets and configuration | Critical |
| `config.yaml` | Runtime configuration | Important |
| `milvus-data` volume | Vector embeddings (RAG) | Nice to have (regenerable) |

### Backup procedure

```bash
# Stop services (optional but recommended for consistency)
docker compose stop

# Back up named volumes
docker run --rm -v purple-pipeline-parser-eater-2_app-data:/data -v $(pwd)/backup:/backup \
  alpine tar czf /backup/app-data-$(date +%Y%m%d).tar.gz -C /data .

docker run --rm -v purple-pipeline-parser-eater-2_app-output:/data -v $(pwd)/backup:/backup \
  alpine tar czf /backup/app-output-$(date +%Y%m%d).tar.gz -C /data .

# Back up env and config
cp .env backup/.env.$(date +%Y%m%d)
cp config.yaml backup/config.yaml.$(date +%Y%m%d) 2>/dev/null

# Restart services
docker compose start
```

### Restore procedure

```bash
docker compose down

# Restore volumes
docker run --rm -v purple-pipeline-parser-eater-2_app-data:/data -v $(pwd)/backup:/backup \
  alpine sh -c "cd /data && tar xzf /backup/app-data-YYYYMMDD.tar.gz"

docker run --rm -v purple-pipeline-parser-eater-2_app-output:/data -v $(pwd)/backup:/backup \
  alpine sh -c "cd /data && tar xzf /backup/app-output-YYYYMMDD.tar.gz"

# Restore config
cp backup/.env.YYYYMMDD .env

docker compose --env-file .env up -d
```

### Milvus data

Milvus vector data can be regenerated from the JSONL correction files in `app-data`. If you lose the Milvus volume, corrections are not lost -- they are replayed from `data/feedback/corrections.jsonl` on the next startup with RAG enabled.
