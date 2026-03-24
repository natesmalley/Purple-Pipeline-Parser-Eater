# Purple Pipeline Parser Eater - Docker & Kubernetes Quick Start
**Version 9.0.0** | FIPS 140-2 Compliant | STIG Hardened

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- Docker 20.10+ or Docker Desktop 4.0+
- Docker Compose 2.0+
- 16GB RAM, 4+ CPU cores, 100GB disk

### Deploy Locally

```bash
# 1. Create data directories
mkdir -p data/{milvus,etcd,minio} output logs

# 2. Configure environment
cp .env.example .env
# Edit .env and change default passwords!

# 3. Update config.yaml with your API keys
nano config.yaml

# 4. Start all services
docker compose up -d

# 5. Check status
docker compose ps

# 6. Access Web UI
open http://localhost:8080
```

## 📚 Documentation

- **[DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)** - Complete deployment guide (15,000+ words)
- **[DEPLOYMENT_COMPLETE.md](DEPLOYMENT_COMPLETE.md)** - Implementation summary
- **[README.md](README.md)** - Project overview

## 🔐 Security Features

- **STIG Compliant**: 10+ controls implemented
- **FIPS 140-2**: Cryptographic compliance enabled
- **Non-root Execution**: UID 999 (appuser)
- **Read-only Filesystem**: Application container
- **Network Isolation**: Private bridge network
- **Resource Limits**: CPU and memory constraints
- **Health Checks**: All services monitored

## 📦 Container Architecture

```
┌─────────────────────────────────────────────────┐
│  Purple Pipeline Parser Eater (Port 8080)      │
│  ├── Continuous Conversion Service              │
│  ├── Web UI (Flask)                             │
│  └── RAG Engine (Milvus client)                 │
└────────────────┬────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
   ┌────▼─────┐    ┌──────▼──────┐
   │  Milvus  │    │   etcd      │
   │  Vector  │◄───┤   Metadata  │
   │  DB      │    │   Store     │
   └────┬─────┘    └─────────────┘
        │
   ┌────▼─────┐
   │  MinIO   │
   │  Object  │
   │  Storage │
   └──────────┘
```

## 🎯 Deployment Options

| Platform | Command | Time | Use Case |
|:---------|:--------|:-----|:---------|
| **Local Docker** | `docker compose up -d` | 5 min | Development, Testing |
| **Kubernetes** | `kubectl apply -f deployment/k8s/base/` | 30 min | On-premise Production |
| **AWS ECS** | See [guide](DOCKER_DEPLOYMENT_GUIDE.md#aws-ecs) | 20 min | Cloud Serverless |
| **AWS EKS** | See [guide](DOCKER_DEPLOYMENT_GUIDE.md#aws-eks) | 30 min | Cloud Kubernetes |

## 🔧 Common Commands

```bash
# Start services
docker compose up -d

# View logs
docker compose logs -f parser-eater

# Check status
docker compose ps

# Stop services
docker compose down

# Rebuild image
docker compose build --no-cache

# Enter container
docker compose exec parser-eater bash

# View resource usage
docker stats
```

## 🩺 Health Checks

```bash
# Application health
curl http://localhost:8080/api/status

# Expected response:
# {
#   "status": "running",
#   "rag_enabled": true,
#   "milvus_connected": true
# }
```

## 📁 Key Files

| File | Purpose |
|:-----|:--------|
| `Dockerfile` | Multi-stage production image |
| `docker-compose.yml` | 4-container orchestration |
| `.dockerignore` | Security exclusions |
| `.env.example` | Environment template |
| `deployment/k8s/base/*.yaml` | Kubernetes manifests |
| `DOCKER_DEPLOYMENT_GUIDE.md` | Complete guide |

## 🔒 Security Compliance

### STIG Controls Implemented
- V-230276: Non-root execution
- V-230285: Read-only root filesystem
- V-230286: Minimal capabilities
- V-230287: No new privileges
- V-230289: Structured logging
- V-230290: Resource limits
- V-242383: RBAC service account
- V-242436: Pod security context
- V-242437: Container security
- V-242438: Pod tolerations

### FIPS 140-2 Compliance
- OpenSSL FIPS mode enabled
- FIPS-validated cryptographic modules
- KMS encryption for persistent volumes

## 🆘 Troubleshooting

### Container fails to start
```bash
docker compose logs parser-eater
docker compose restart parser-eater
```

### Milvus connection failed
```bash
docker compose ps milvus
docker compose logs milvus
```

### Out of memory
```bash
# Edit .env
echo "APP_MEMORY_LIMIT=16G" >> .env
docker compose down && docker compose up -d
```

## 📊 Resource Requirements

### Minimum
- CPU: 2 cores
- RAM: 8GB
- Disk: 50GB

### Recommended
- CPU: 4+ cores
- RAM: 16GB
- Disk: 100GB+

### Production
- CPU: 8+ cores
- RAM: 32GB
- Disk: 500GB+ (SSD)

## 🎓 Next Steps

1. Review [DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)
2. Choose deployment platform
3. Configure secrets (`.env`, `config.yaml`)
4. Deploy services
5. Verify health checks
6. Access Web UI at http://localhost:8080

## 📞 Support

- **Documentation**: See [DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)
- **Issues**: GitHub Issues
- **Security**: Report via email

---

**Purple Pipeline Parser Eater v9.0.0**
Containerized | Secured | Ready for Deployment
