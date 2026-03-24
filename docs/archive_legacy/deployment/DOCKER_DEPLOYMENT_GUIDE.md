# Purple Pipeline Parser Eater - Docker Deployment Guide
**Version 9.0.0** | FIPS 140-2 Compliant | STIG Hardened | Production Ready

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Security Architecture](#security-architecture)
4. [Local Docker Deployment](#local-docker-deployment)
5. [Docker Compose Production Deployment](#docker-compose-production-deployment)
6. [Kubernetes Deployment](#kubernetes-deployment)
7. [AWS Deployment](#aws-deployment)
8. [Security Hardening](#security-hardening)
9. [Monitoring and Logging](#monitoring-and-logging)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The Purple Pipeline Parser Eater is containerized for deployment across multiple environments:
- **Local Development**: Docker Compose on workstation
- **Production On-Premise**: Kubernetes cluster
- **Cloud Production**: AWS ECS/EKS with full compliance

### Architecture Components
```
┌─────────────────────────────────────────────────┐
│  Purple Pipeline Parser Eater System            │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌───────────────────┐  ┌──────────────────┐   │
│  │  Parser Eater App │  │   Milvus Vector  │   │
│  │  - Web UI (8080)  │──│   Database       │   │
│  │  - RAG Engine     │  │   - Port 19530   │   │
│  │  - Conversion     │  └──────────────────┘   │
│  └───────────────────┘           │              │
│           │                      │              │
│           │         ┌────────────┴─────────┐    │
│           │         │                      │    │
│  ┌────────┴──────┐  │  ┌────────┐  ┌──────┴──┐ │
│  │  Persistent   │  └──│  etcd  │  │  MinIO  │ │
│  │  Volumes      │     │        │  │         │ │
│  │  - Output     │     └────────┘  └─────────┘ │
│  │  - Logs       │                              │
│  │  - Data       │                              │
│  └───────────────┘                              │
└─────────────────────────────────────────────────┘
```

---

## Prerequisites

### System Requirements
- **CPU**: 4+ cores recommended (2 minimum)
- **RAM**: 16GB recommended (8GB minimum)
- **Disk**: 100GB+ free space
- **OS**: Linux, macOS, Windows with WSL2

### Software Requirements
- Docker 20.10+ or Docker Desktop 4.0+
- Docker Compose 2.0+ (or `docker compose` plugin)
- Git 2.0+
- (Optional) kubectl 1.24+ for Kubernetes
- (Optional) AWS CLI 2.0+ for AWS deployment

### Network Requirements
- Internet access for:
  - GitHub API (api.github.com)
  - Anthropic API (api.anthropic.com)
  - Docker Hub (for base images)
- Port 8080 available for Web UI

---

## Security Architecture

### STIG Compliance Implementation

| STIG Control | Implementation | Status |
|:-------------|:---------------|:------:|
| V-230276 | Non-root container execution (UID 999) | ✅ |
| V-230285 | Read-only root filesystem | ✅ |
| V-230286 | Minimal Linux capabilities | ✅ |
| V-230287 | No new privileges flag | ✅ |
| V-230289 | Structured logging with rotation | ✅ |
| V-230290 | Resource limits (CPU/Memory) | ✅ |
| V-242383 | Minimal service account permissions | ✅ |
| V-242415 | Sensitive data classification | ✅ |

### FIPS 140-2 Compliance

- **OpenSSL FIPS Mode**: Enabled via `OPENSSL_FIPS=1`
- **Cryptographic Operations**: Using FIPS-validated modules
- **Python Compliance**: `PYTHONHASHSEED=0` for deterministic behavior
- **TLS/SSL**: FIPS-approved cipher suites only

### Security Features

- ✅ Multi-stage Docker build (minimal attack surface)
- ✅ Non-root user execution (UID 999)
- ✅ Read-only root filesystem
- ✅ Dropped Linux capabilities
- ✅ Network isolation (private Docker network)
- ✅ Secrets management (environment variables)
- ✅ Health checks on all services
- ✅ Resource constraints
- ✅ Log rotation

---

## Local Docker Deployment

### Quick Start (5 Minutes)

```bash
# 1. Clone repository
git clone https://github.com/your-org/Purple-Pipeline-Parser-Eater.git
cd Purple-Pipeline-Parser-Eater/purple-pipeline-parser-eater

# 2. Run preparation script
./prepare-docker-deployment.sh
# Or on Windows: powershell -ExecutionPolicy Bypass -File prepare-docker-deployment.ps1

# 3. Configure secrets
cp .env.example .env
nano .env  # Edit with your credentials

# 4. Update config.yaml with your API keys

# 5. Start services
docker compose up -d

# 6. Monitor startup
docker compose logs -f parser-eater

# 7. Access Web UI
open http://localhost:8080
```

### Step-by-Step Deployment

#### Step 1: Prepare Environment

```bash
# Create data directories
mkdir -p data/{milvus,etcd,minio} output logs data

# Set secure permissions
chmod 750 data output logs
chmod 750 data/{milvus,etcd,minio}
```

#### Step 2: Configure Secrets

Edit `.env` file:
```bash
# MinIO Credentials (CHANGE THESE!)
MINIO_ACCESS_KEY=your-secure-access-key-here
MINIO_SECRET_KEY=your-secure-secret-key-here

# Resource Limits
APP_CPU_LIMIT=4
APP_MEMORY_LIMIT=8G
```

Edit `config.yaml`:
```yaml
anthropic:
  api_key: "sk-ant-api03-YOUR-KEY-HERE"

github:
  token: "github_pat_YOUR-TOKEN-HERE"
```

#### Step 3: Build Docker Image

```bash
# Build application image
docker build -t purple-pipeline-parser-eater:9.0.0 -f Dockerfile .

# Verify image
docker images | grep purple-pipeline

# Check image size (should be 2-3GB)
docker images purple-pipeline-parser-eater:9.0.0 --format "{{.Size}}"
```

#### Step 4: Start Services

```bash
# Start all services in detached mode
docker compose up -d

# Expected output:
#  ✔ Network purple-parser-network     Created
#  ✔ Container purple-minio            Started
#  ✔ Container purple-etcd             Started
#  ✔ Container purple-milvus           Healthy
#  ✔ Container purple-parser-eater     Started
```

#### Step 5: Verify Deployment

```bash
# Check container status
docker compose ps

# Should show all containers as "Up" and "healthy"

# Check logs
docker compose logs parser-eater | tail -50

# Test Web UI
curl http://localhost:8080/api/status

# Expected response:
# {
#   "status": "running",
#   "rag_enabled": true,
#   "milvus_connected": true,
#   "pending_conversions": 0
# }
```

#### Step 6: Access Web UI

Open browser to: **http://localhost:8080**

You should see the Purple Pipeline Parser Eater web interface with:
- System status dashboard
- Pending conversions list
- Approve/Reject/Modify actions
- Real-time statistics

---

## Docker Compose Production Deployment

### Production Configuration

The included `docker-compose.yml` is production-ready with:

- **Security Hardening**: All STIG controls implemented
- **Resource Limits**: CPU and memory constraints
- **Health Checks**: All services monitored
- **Logging**: JSON structured logging with rotation
- **Network Isolation**: Private bridge network
- **Persistent Storage**: Named volumes for data

### Production Checklist

- [ ] Change all default passwords in `.env`
- [ ] Update API keys in `config.yaml`
- [ ] Review resource limits for your hardware
- [ ] Enable firewall rules (allow port 8080)
- [ ] Set up TLS/SSL reverse proxy (nginx/traefik)
- [ ] Configure log aggregation (ELK/Splunk)
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Implement backup strategy
- [ ] Document runbook procedures

### Production Commands

```bash
# Start services
docker compose up -d

# Monitor all services
docker compose logs -f

# Monitor specific service
docker compose logs -f parser-eater

# Check service health
docker compose ps

# Restart specific service
docker compose restart parser-eater

# Stop all services
docker compose down

# Stop and remove volumes (DESTRUCTIVE!)
docker compose down -v

# View resource usage
docker stats

# Execute command in container
docker compose exec parser-eater bash
```

### Backup and Restore

```bash
# Backup volumes
docker compose down
tar czf backup-$(date +%Y%m%d).tar.gz data/ output/ logs/

# Restore volumes
tar xzf backup-20250108.tar.gz
docker compose up -d

# Backup Milvus data only
docker compose exec milvus tar czf - /var/lib/milvus > milvus-backup.tar.gz
```

---

## Kubernetes Deployment

See [deployment/k8s/README.md](deployment/k8s/README.md) for complete Kubernetes deployment guide.

### Quick Kubernetes Deployment

```bash
# Apply all manifests
kubectl apply -f deployment/k8s/base/

# Check deployment status
kubectl get all -n purple-parser

# Check pod logs
kubectl logs -f -n purple-parser deployment/purple-parser-app

# Access Web UI (port-forward)
kubectl port-forward -n purple-parser service/purple-parser-web-ui 8080:8080

# Access Web UI in browser
open http://localhost:8080
```

---

## AWS Deployment

### Architecture Options

#### Option 1: AWS ECS with Fargate (Serverless)
- **Pros**: Fully managed, no server management, scales automatically
- **Cons**: Higher cost per task, less control
- **Best for**: Variable workloads, rapid deployment

#### Option 2: AWS EKS (Kubernetes)
- **Pros**: Full Kubernetes features, multi-cloud portability, extensive ecosystem
- **Cons**: Complex setup, requires Kubernetes expertise
- **Best for**: Enterprise deployments, multi-cloud strategy

#### Option 3: EC2 with Docker Compose
- **Pros**: Simple, cost-effective, full control
- **Cons**: Manual management, no auto-scaling
- **Best for**: Development, testing, proof-of-concept

### AWS ECS Deployment Guide

#### Prerequisites

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure AWS credentials
aws configure
# AWS Access Key ID: YOUR_ACCESS_KEY
# AWS Secret Access Key: YOUR_SECRET_KEY
# Default region: us-east-1
# Default output format: json

# Install ECS CLI
sudo curl -Lo /usr/local/bin/ecs-cli https://amazon-ecs-cli.s3.amazonaws.com/ecs-cli-linux-amd64-latest
sudo chmod +x /usr/local/bin/ecs-cli
```

#### Step 1: Create ECR Repository

```bash
# Create repository for Docker image
aws ecr create-repository \
    --repository-name purple-pipeline-parser-eater \
    --region us-east-1 \
    --encryption-configuration encryptionType=KMS  # STIG compliance

# Get repository URI
ECR_URI=$(aws ecr describe-repositories \
    --repository-name purple-pipeline-parser-eater \
    --query 'repositories[0].repositoryUri' \
    --output text)

echo "ECR Repository: $ECR_URI"
```

#### Step 2: Build and Push Docker Image

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin $ECR_URI

# Build image
docker build -t purple-pipeline-parser-eater:9.0.0 .

# Tag for ECR
docker tag purple-pipeline-parser-eater:9.0.0 $ECR_URI:9.0.0
docker tag purple-pipeline-parser-eater:9.0.0 $ECR_URI:latest

# Push to ECR
docker push $ECR_URI:9.0.0
docker push $ECR_URI:latest
```

#### Step 3: Create ECS Cluster

```bash
# Create ECS cluster with Fargate
aws ecs create-cluster \
    --cluster-name purple-parser-cluster \
    --region us-east-1 \
    --capacity-providers FARGATE FARGATE_SPOT \
    --default-capacity-provider-strategy \
        capacityProvider=FARGATE,weight=1,base=1 \
        capacityProvider=FARGATE_SPOT,weight=4

# Verify cluster
aws ecs describe-clusters --clusters purple-parser-cluster
```

#### Step 4: Create Task Definition

Create `ecs-task-definition.json`:

```json
{
  "family": "purple-parser-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "8192",
  "executionRoleArn": "arn:aws:iam::YOUR_ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::YOUR_ACCOUNT:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "parser-eater",
      "image": "YOUR_ECR_URI:9.0.0",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "APP_ENV", "value": "production"},
        {"name": "MILVUS_HOST", "value": "milvus"},
        {"name": "PYTHONUNBUFFERED", "value": "1"},
        {"name": "OPENSSL_FIPS", "value": "1"}
      ],
      "secrets": [
        {
          "name": "ANTHROPIC_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT:secret:purple-parser/anthropic-api-key"
        },
        {
          "name": "GITHUB_TOKEN",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT:secret:purple-parser/github-token"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/purple-parser",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "parser-eater"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/api/status || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 120
      }
    }
  ]
}
```

Register task definition:
```bash
aws ecs register-task-definition \
    --cli-input-json file://ecs-task-definition.json
```

#### Step 5: Create ECS Service

```bash
# Create security group
SG_ID=$(aws ec2 create-security-group \
    --group-name purple-parser-sg \
    --description "Purple Parser security group" \
    --vpc-id YOUR_VPC_ID \
    --query 'GroupId' \
    --output text)

# Allow inbound traffic on port 8080
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 8080 \
    --cidr 0.0.0.0/0  # Restrict this in production!

# Create ECS service
aws ecs create-service \
    --cluster purple-parser-cluster \
    --service-name purple-parser-service \
    --task-definition purple-parser-task \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[YOUR_SUBNET_ID],securityGroups=[$SG_ID],assignPublicIp=ENABLED}"
```

#### Step 6: Verify Deployment

```bash
# Check service status
aws ecs describe-services \
    --cluster purple-parser-cluster \
    --services purple-parser-service

# Get task ID
TASK_ARN=$(aws ecs list-tasks \
    --cluster purple-parser-cluster \
    --service-name purple-parser-service \
    --query 'taskArns[0]' \
    --output text)

# Get public IP
PUBLIC_IP=$(aws ecs describe-tasks \
    --cluster purple-parser-cluster \
    --tasks $TASK_ARN \
    --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
    --output text | xargs -I {} aws ec2 describe-network-interfaces \
    --network-interface-ids {} \
    --query 'NetworkInterfaces[0].Association.PublicIp' \
    --output text)

echo "Web UI: http://$PUBLIC_IP:8080"

# Test deployment
curl http://$PUBLIC_IP:8080/api/status
```

### AWS EKS Deployment Guide

#### Prerequisites

```bash
# Install eksctl
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
sudo mv /tmp/eksctl /usr/local/bin

# Verify installation
eksctl version
```

#### Step 1: Create EKS Cluster

```bash
# Create EKS cluster (this takes 15-20 minutes)
eksctl create cluster \
    --name purple-parser-cluster \
    --region us-east-1 \
    --nodegroup-name standard-workers \
    --node-type t3.xlarge \
    --nodes 2 \
    --nodes-min 1 \
    --nodes-max 4 \
    --managed \
    --ssh-access \
    --ssh-public-key YOUR_SSH_KEY

# Verify cluster
kubectl get nodes
```

#### Step 2: Deploy Application

```bash
# Apply Kubernetes manifests
kubectl apply -f deployment/k8s/base/

# Check deployment status
kubectl get all -n purple-parser

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=purple-pipeline-parser-eater -n purple-parser --timeout=300s
```

#### Step 3: Expose Service

```bash
# Create LoadBalancer service (AWS will provision ELB)
kubectl expose deployment purple-parser-app \
    --type=LoadBalancer \
    --port=80 \
    --target-port=8080 \
    --name=purple-parser-lb \
    -n purple-parser

# Get LoadBalancer URL (may take a few minutes)
kubectl get service purple-parser-lb -n purple-parser

# Access Web UI
LB_URL=$(kubectl get service purple-parser-lb -n purple-parser -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "Web UI: http://$LB_URL"
```

---

## Security Hardening

### TLS/SSL Configuration

#### Using nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/purple-parser

server {
    listen 443 ssl http2;
    server_name parser.example.com;

    # TLS Configuration (FIPS-approved ciphers)
    ssl_certificate /etc/ssl/certs/purple-parser.crt;
    ssl_certificate_key /etc/ssl/private/purple-parser.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Secrets Management

#### AWS Secrets Manager Integration

```bash
# Store secrets in AWS Secrets Manager
aws secretsmanager create-secret \
    --name purple-parser/anthropic-api-key \
    --secret-string "sk-ant-api03-YOUR-KEY"

aws secretsmanager create-secret \
    --name purple-parser/github-token \
    --secret-string "github_pat_YOUR-TOKEN"

# Grant ECS task role access
aws iam put-role-policy \
    --role-name ecsTaskRole \
    --policy-name SecretsManagerAccess \
    --policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Action": [
          "secretsmanager:GetSecretValue"
        ],
        "Resource": [
          "arn:aws:secretsmanager:*:*:secret:purple-parser/*"
        ]
      }]
    }'
```

---

## Monitoring and Logging

### Health Checks

```bash
# Application health
curl http://localhost:8080/api/status

# Milvus health
curl http://localhost:9091/healthz

# Docker container health
docker compose ps
```

### Logs

```bash
# View application logs
docker compose logs parser-eater

# Follow logs in real-time
docker compose logs -f parser-eater

# View last 100 lines
docker compose logs --tail=100 parser-eater

# Export logs to file
docker compose logs parser-eater > parser-eater.log
```

### Monitoring with Prometheus

Access Prometheus metrics:
```bash
curl http://localhost:9090/metrics
```

---

## Troubleshooting

### Common Issues

#### Issue: Container fails to start

```bash
# Check logs
docker compose logs parser-eater

# Check container health
docker inspect purple-parser-eater | grep Health

# Restart container
docker compose restart parser-eater
```

#### Issue: Milvus connection failed

```bash
# Check Milvus is running
docker compose ps milvus

# Check Milvus logs
docker compose logs milvus

# Test Milvus connection
curl http://localhost:9091/healthz
```

#### Issue: Out of memory

```bash
# Check resource usage
docker stats

# Increase memory limit in .env
echo "APP_MEMORY_LIMIT=16G" >> .env

# Restart services
docker compose down
docker compose up -d
```

#### Issue: Permission denied

```bash
# Fix directory permissions
sudo chown -R 999:999 data/ output/ logs/
chmod 750 data output logs
```

### Debug Mode

```bash
# Run container with debug shell
docker compose exec parser-eater bash

# Check Python environment
python --version
pip list

# Test connectivity
curl http://localhost:8080/api/status
```

---

## Support

For issues and support:
- GitHub Issues: https://github.com/your-org/Purple-Pipeline-Parser-Eater/issues
- Documentation: https://docs.purple-parser.example.com
- Email: support@example.com

---

**Purple Pipeline Parser Eater v9.0.0**
FIPS 140-2 Compliant | STIG Hardened | Production Ready
