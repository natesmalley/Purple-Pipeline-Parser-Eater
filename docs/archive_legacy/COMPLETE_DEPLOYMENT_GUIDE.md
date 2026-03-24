# Purple Pipeline Parser Eater - Complete Deployment Guide

**Version**: 1.0
**Date**: 2025-11-08
**Status**: Production Ready

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Deployment Options](#deployment-options)
3. [Kubernetes Deployment](#kubernetes-deployment)
4. [VM Deployment](#vm-deployment)
5. [AWS Deployment](#aws-deployment)
6. [GCP Deployment](#gcp-deployment)
7. [Post-Deployment](#post-deployment)
8. [Operational Management](#operational-management)
9. [Troubleshooting](#troubleshooting)
10. [Disaster Recovery](#disaster-recovery)

---

## Quick Start

### Choose Your Deployment Type

Choose the deployment method that best fits your needs:

| Method | Setup Time | Complexity | Scalability | Cost |
|--------|-----------|-----------|-------------|------|
| **Docker Compose** (Local) | 5 min | Very Low | Limited | Free |
| **Single VM** | 30 min | Low | Manual | $30-50/mo |
| **Kubernetes (any cloud)** | 45 min | Medium | Automatic | $200-350/mo |
| **AWS EKS** | 60 min | High | Automatic | $273-703/mo |
| **GCP GKE** | 60 min | High | Automatic | $200-385/mo |

### Minimum Requirements

**For all deployments**:
- Docker/container runtime
- 4GB RAM minimum
- 20GB disk space minimum
- Network access to external APIs (Claude, Observo)

---

## Deployment Options

### Option 1: Local Development (Docker Compose)

**Time**: 5 minutes
**Complexity**: Very Low
**Best For**: Local testing, development

```bash
# Clone repository
git clone https://github.com/jhexiS1/Purple-Pipline-Parser-Eater.git
cd Purple-Pipline-Parser-Eater

# Start services
docker-compose up -d

# Verify
curl http://localhost:8080/health
```

**Components**:
- Purple Pipeline web UI (port 8080)
- Prometheus (port 9090)
- Milvus (port 19530)
- Kafka (port 9092)
- Redis (port 6379)

---

### Option 2: Single VM Deployment

**Time**: 30 minutes
**Complexity**: Low
**Best For**: Small deployments, testing, single-server setup

#### Prerequisites

- Ubuntu 22.04 LTS or Debian 11+
- 4GB RAM, 20GB disk
- Root/sudo access
- Internet connectivity

#### Step-by-Step

```bash
# 1. SSH into VM
ssh ubuntu@<vm-ip>

# 2. Download and run deployment script
curl -fsSL https://raw.githubusercontent.com/jhexiS1/Purple-Pipline-Parser-Eater/main/deployment/vm/deploy.sh | sudo bash

# 3. Configure environment
sudo vi /etc/purple-parser-eater/purple-parser-eater.conf

# 4. Restart service
sudo systemctl restart purple-parser-eater

# 5. Verify
curl http://localhost:8080/health
sudo systemctl status purple-parser-eater
```

#### Management

```bash
# Service management
sudo systemctl start purple-parser-eater
sudo systemctl stop purple-parser-eater
sudo systemctl restart purple-parser-eater
sudo systemctl status purple-parser-eater

# Logs
sudo journalctl -u purple-parser-eater -f
sudo journalctl -u purple-parser-eater --since "1 hour ago"

# Updates
cd /opt/purple-parser-eater
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart purple-parser-eater
```

---

### Option 3: Kubernetes Deployment

**Time**: 45 minutes
**Complexity**: Medium
**Best For**: Production, cloud-native, auto-scaling

#### Prerequisites

- Kubernetes cluster 1.24+ (EKS, GKE, AKS, or minikube)
- `kubectl` configured and connected
- `kustomize` or `kubectl` with kustomize support

#### Deployment

```bash
# 1. Clone repository
git clone https://github.com/jhexiS1/Purple-Pipline-Parser-Eater.git
cd Purple-Pipline-Parser-Eater

# 2. Deploy to your environment
./deployment/k8s/deploy.sh -e production

# Or manually:
kubectl apply -k deployment/k8s/overlays/production

# 3. Verify
kubectl get pods -n purple-pipeline-prod
kubectl logs -n purple-pipeline-prod -f deployment/prod-purple-parser-eater

# 4. Access application
kubectl port-forward -n purple-pipeline-prod svc/prod-purple-parser-eater 8080:8080
# Access at http://localhost:8080
```

#### Environment-Specific Deployment

```bash
# Development
./deployment/k8s/deploy.sh -e dev

# Staging
./deployment/k8s/deploy.sh -e staging

# Production
./deployment/k8s/deploy.sh -e production
```

#### Kustomize Overlay Structure

```
deployment/k8s/
├── base/                           # Shared base
│   ├── deployment-app.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── kustomization.yaml
│
└── overlays/
    ├── dev/                        # Development (1 replica, loose limits)
    │   └── kustomization.yaml
    ├── staging/                    # Staging (2 replicas, moderate limits)
    │   └── kustomization.yaml
    └── production/                 # Production (3 replicas, strict limits)
        └── kustomization.yaml
```

#### Kubernetes Management

```bash
# View resources
kubectl get pods -n purple-pipeline-prod
kubectl get services -n purple-pipeline-prod
kubectl get ingress -n purple-pipeline-prod

# Scaling
kubectl scale deployment/prod-purple-parser-eater --replicas=5 -n purple-pipeline-prod

# Update image
kubectl set image deployment/prod-purple-parser-eater \
  purple-parser-eater=gcr.io/project/purple-parser-eater:v1.1.0 \
  -n purple-pipeline-prod

# Logs
kubectl logs -f deployment/prod-purple-parser-eater -n purple-pipeline-prod
kubectl logs -f pod/prod-purple-parser-eater-xxxx -n purple-pipeline-prod

# Port forward
kubectl port-forward svc/prod-purple-parser-eater 8080:8080 -n purple-pipeline-prod
```

---

## Kubernetes Deployment

### Complete Setup with Terraform

```bash
cd deployment/k8s/terraform

# Initialize
terraform init

# Plan
terraform plan -out=tfplan

# Apply
terraform apply tfplan

# Configure kubectl
eval $(terraform output configure_kubectl)

# Deploy application
./deploy.sh -e production
```

### High Availability Configuration

**Production defaults**:
- 3 replicas (minimum)
- Pod anti-affinity (spread across nodes)
- Health checks (startup, readiness, liveness)
- Resource limits (500m CPU request, 2GB memory limit)
- Auto-scaling: 3-10 replicas based on CPU/memory
- Pod Disruption Budget: minimum 2 available

### Network Configuration

**Ingress**:
- TLS termination with Let's Encrypt
- Automatic certificate renewal
- Rate limiting (100 req/sec)
- CORS configured for Observo.ai

**NetworkPolicy**:
- Default deny all
- Allow from ingress controller
- Allow Prometheus scraping
- Allow external APIs (Claude, Observo)
- Restrict inter-pod communication

---

## AWS Deployment

### Option A: AWS EKS (Recommended)

**Time**: 60 minutes
**Features**: Fully managed K8s, auto-scaling, high availability

```bash
cd deployment/aws/terraform

# Configure
cat > terraform.tfvars << EOF
aws_region         = "us-east-1"
environment        = "production"
cluster_name       = "purple-pipeline"
kubernetes_version = "1.27"

# Sizing
node_desired_count = 3
node_instance_type = "t3.large"
EOF

# Deploy
terraform init
terraform plan
terraform apply

# Configure kubectl
aws eks update-kubeconfig --name purple-pipeline --region us-east-1

# Deploy application
kubectl apply -k deployment/k8s/overlays/production
```

**AWS Services Deployed**:
- EKS Cluster (managed Kubernetes)
- EC2 Auto Scaling Groups (nodes)
- RDS PostgreSQL (multi-AZ)
- ElastiCache Redis (multi-AZ)
- MSK Kafka (3 brokers)
- Application Load Balancer (ALB)
- Route 53 (DNS)
- CloudWatch (logging/monitoring)
- Secrets Manager (credentials)
- S3 (backups, logs)

**Estimated Cost**:
- Control Plane: $73/month
- 3x t3.large nodes: $180/month
- RDS multi-AZ: $150/month
- ElastiCache: $30/month
- MSK Kafka: $200/month
- Load Balancing: $20/month
- **Total**: ~$653/month

### Option B: AWS EC2 (Traditional VMs)

**Time**: 45 minutes
**Features**: Traditional VMs with auto-scaling

```bash
cd deployment/aws/terraform

# Configure for EC2
cat > terraform.tfvars << EOF
aws_region   = "us-east-1"
environment  = "production"
deployment_type = "ec2"  # Instead of eks

# Instance sizing
instance_type = "t3.medium"
desired_count = 2
max_count = 5
EOF

# Deploy
terraform apply

# Script will automatically configure instances via user data
```

---

## GCP Deployment

### Option A: Google Kubernetes Engine (GKE)

**Time**: 60 minutes
**Features**: Managed Kubernetes on GCP

```bash
cd deployment/gcp/terraform

# Configure
cat > terraform.tfvars << EOF
gcp_project_id  = "your-project-id"
gcp_region      = "us-central1"
cluster_name    = "purple-pipeline"
environment     = "production"
node_count      = 3
machine_type    = "n1-standard-2"
EOF

# Deploy
terraform init
terraform plan
terraform apply

# Configure kubectl
gcloud container clusters get-credentials purple-pipeline --zone us-central1-a

# Deploy application
kubectl apply -k deployment/k8s/overlays/production
```

**GCP Services**:
- GKE (managed Kubernetes)
- Compute Engine (nodes, auto-scaling)
- Cloud SQL (PostgreSQL, HA)
- Memorystore (Redis)
- Cloud Pub/Sub (Kafka alternative)
- Cloud Load Balancing
- Cloud DNS
- Cloud Monitoring
- Secret Manager

**Estimated Cost**:
- GKE (no control plane fee): Included
- 3x n1-standard-2 nodes: $150/month
- Cloud SQL: $120/month
- Memorystore: $15/month
- Load Balancing: $40/month
- **Total**: ~$325/month

### Option B: Google Compute Engine

**Time**: 45 minutes
**Features**: Traditional VMs with managed groups

```bash
cd deployment/gcp/terraform

# Configure
cat > terraform.tfvars << EOF
gcp_project_id  = "your-project-id"
gcp_region      = "us-central1"
deployment_type = "compute-engine"
machine_type    = "n1-standard-2"
EOF

terraform apply
```

---

## Post-Deployment

### 1. Verify Installation

```bash
# Check all pods are running
kubectl get pods -n purple-pipeline-prod

# Check services
kubectl get svc -n purple-pipeline-prod

# Check ingress
kubectl get ingress -n purple-pipeline-prod

# Test health endpoint
curl https://purple-parser.example.com/health
```

### 2. Configure DNS

```bash
# AWS Route 53
aws route53 change-resource-record-sets \
  --hosted-zone-id Z... \
  --change-batch file://dns-change.json

# GCP Cloud DNS
gcloud dns record-sets create purple-parser.example.com \
  --rrdatas=<ALB_or_LB_IP> \
  --ttl=300 \
  --type=A \
  --zone=example-com
```

### 3. Setup Monitoring

```bash
# Prometheus scraping
kubectl apply -f external-monitoring/prometheus-configmap.yaml

# Grafana dashboards
kubectl apply -f external-monitoring/grafana-dashboards.yaml

# Alert rules
kubectl apply -f external-monitoring/alert-rules.yaml

# Access Grafana
kubectl port-forward svc/grafana 3000:3000 -n monitoring
# Visit http://localhost:3000 (admin/admin)
```

### 4. Configure Backups

```bash
# AWS: Enable RDS automated backups
aws rds modify-db-instance \
  --db-instance-identifier purple-pipeline \
  --backup-retention-period 30

# GCP: Enable Cloud SQL backups
gcloud sql backups create purple-pipeline \
  --instance=purple-pipeline
```

---

## Operational Management

### Daily Operations

```bash
# Check system health
curl https://purple-parser.example.com/health

# View Prometheus metrics
curl https://prometheus.example.com/metrics

# Check logs
kubectl logs -f deployment/prod-purple-parser-eater -n purple-pipeline-prod

# Monitor resources
kubectl top nodes
kubectl top pods -n purple-pipeline-prod
```

### Regular Maintenance

```bash
# Update application
git pull origin main
docker build -t gcr.io/project/purple-parser-eater:v1.1.0 .
docker push gcr.io/project/purple-parser-eater:v1.1.0

kubectl set image deployment/prod-purple-parser-eater \
  purple-parser-eater=gcr.io/project/purple-parser-eater:v1.1.0 \
  -n purple-pipeline-prod

# Verify rollout
kubectl rollout status deployment/prod-purple-parser-eater -n purple-pipeline-prod

# Scaling
kubectl scale deployment/prod-purple-parser-eater --replicas=5 -n purple-pipeline-prod
```

---

## Troubleshooting

### Application Won't Start

```bash
# Check pod status
kubectl describe pod <pod-name> -n purple-pipeline-prod

# Check logs
kubectl logs <pod-name> -n purple-pipeline-prod
kubectl logs <pod-name> --previous -n purple-pipeline-prod

# Check events
kubectl get events -n purple-pipeline-prod --sort-by='.lastTimestamp'

# Debug container
kubectl debug pod/<pod-name> -n purple-pipeline-prod -it --image=busybox
```

### High Resource Usage

```bash
# Check resource requests/limits
kubectl describe deployment prod-purple-parser-eater -n purple-pipeline-prod

# Check actual usage
kubectl top pods -n purple-pipeline-prod

# Adjust limits
kubectl set resources deployment prod-purple-parser-eater \
  --limits=cpu=2000m,memory=2Gi \
  --requests=cpu=500m,memory=512Mi \
  -n purple-pipeline-prod
```

### Database Connection Issues

```bash
# Test database connectivity
kubectl exec -it <pod> -n purple-pipeline-prod -- \
  psql -h <db-host> -U purple_parser -d purple_pipeline

# Check database status
# AWS: aws rds describe-db-instances --db-instance-identifier purple-pipeline
# GCP: gcloud sql instances describe purple-pipeline
```

### TLS Certificate Issues

```bash
# Check certificate status
kubectl get certificate -n purple-pipeline-prod

# Describe cert
kubectl describe certificate purple-parser-eater-tls -n purple-pipeline-prod

# Check cert-manager logs
kubectl logs -f deployment/cert-manager -n cert-manager

# Manually renew
kubectl delete secret purple-parser-eater-tls -n purple-pipeline-prod
# cert-manager will auto-renew
```

---

## Disaster Recovery

### Backup Strategy

**Database Backups**:
- Daily snapshots (30-day retention)
- Automated backup window: 02:00-03:00 UTC
- Cross-region replicas in production

**Configuration Backups**:
- Infrastructure as Code (Terraform)
- Kubernetes manifests (git version control)
- Secrets in AWS Secrets Manager / GCP Secret Manager

### Recovery Procedures

#### Database Recovery

```bash
# AWS RDS
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier purple-pipeline-restored \
  --db-snapshot-identifier <snapshot-id>

# GCP Cloud SQL
gcloud sql backups describe <backup-id> \
  --instance purple-pipeline
gcloud sql backups restore <backup-id> \
  --backup-configuration default \
  --instance purple-pipeline
```

#### Application Recovery

```bash
# Rollback to previous version
kubectl rollout undo deployment/prod-purple-parser-eater -n purple-pipeline-prod

# Rollback to specific revision
kubectl rollout history deployment/prod-purple-parser-eater -n purple-pipeline-prod
kubectl rollout undo deployment/prod-purple-parser-eater \
  --to-revision=5 -n purple-pipeline-prod
```

#### Full Cluster Recovery

```bash
# From Terraform state
terraform destroy
terraform apply

# Redeploy application
kubectl apply -k deployment/k8s/overlays/production
```

---

## Support & Resources

- **Repository**: https://github.com/jhexiS1/Purple-Pipline-Parser-Eater
- **Documentation**: See `/docs` directory
- **Issues**: GitHub Issues
- **Contributing**: See CONTRIBUTING.md

---

**Deployment Status**: ✅ READY FOR PRODUCTION

All deployment options are fully tested and production-ready. Choose the option that best fits your infrastructure needs and operational capabilities.
