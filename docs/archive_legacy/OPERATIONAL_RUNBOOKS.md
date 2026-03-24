# Purple Pipeline Parser Eater - Operational Runbooks

**Version**: 1.0
**Date**: 2025-11-08
**Status**: Complete

---

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Scaling Operations](#scaling-operations)
3. [Backup and Recovery](#backup-and-recovery)
4. [Troubleshooting](#troubleshooting)
5. [Incident Response](#incident-response)
6. [Maintenance Windows](#maintenance-windows)
7. [Performance Tuning](#performance-tuning)

---

## Daily Operations

### Health Checks

Perform health checks every 4 hours during business hours, or continuously via automated monitoring.

#### Kubernetes (GKE/EKS)

```bash
# Check cluster health
kubectl cluster-info

# Check all nodes
kubectl get nodes -o wide

# Check pod status
kubectl get pods -n purple-pipeline -o wide

# Check services
kubectl get svc -n purple-pipeline

# Check resource usage
kubectl top nodes
kubectl top pods -n purple-pipeline

# Check recent events
kubectl get events -n purple-pipeline --sort-by='.lastTimestamp'

# Verify DNS
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup purple-parser-eater
```

#### VM Deployment

```bash
# SSH to VM
ssh -i /path/to/key ubuntu@<vm-ip>

# Check service status
sudo systemctl status purple-parser-eater

# View recent logs
sudo journalctl -u purple-parser-eater -n 50

# Check system resources
top
df -h
free -h

# Check application health
curl http://localhost:8080/health
```

#### Application Health Endpoint

```bash
# Test health endpoint
curl -v http://localhost:8080/health

# Expected response:
# HTTP/1.1 200 OK
# {
#   "status": "healthy",
#   "timestamp": "2025-11-08T10:30:45Z",
#   "version": "1.0.0"
# }
```

### Log Review

#### Kubernetes Logs

```bash
# Stream logs from all replicas
kubectl logs -f deployment/purple-parser-eater -n purple-pipeline --all-containers=true

# Logs from specific pod
kubectl logs -f pod/purple-parser-eater-xxxxx -n purple-pipeline

# Logs with timestamps
kubectl logs deployment/purple-parser-eater -n purple-pipeline --timestamps=true

# Filter by severity
kubectl logs deployment/purple-parser-eater -n purple-pipeline | grep ERROR

# Last 100 lines
kubectl logs deployment/purple-parser-eater -n purple-pipeline --tail=100
```

#### VM Logs

```bash
# Real-time logs
sudo journalctl -u purple-parser-eater -f

# Last 100 lines
sudo journalctl -u purple-parser-eater -n 100

# Logs from last hour
sudo journalctl -u purple-parser-eater --since "1 hour ago"

# Logs with full details
sudo journalctl -u purple-parser-eater -o verbose

# Filter by priority
sudo journalctl -u purple-parser-eater -p err
```

### Metrics and Monitoring

#### Prometheus Queries

```bash
# Query error rate (5-minute average)
curl 'http://prometheus:9090/api/v1/query?query=rate(purple_events_failed_total[5m])'

# Query event processing rate
curl 'http://prometheus:9090/api/v1/query?query=rate(purple_events_processed_total[5m])'

# Query p95 latency
curl 'http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,rate(purple_parser_execution_duration_seconds_bucket[5m]))'

# Query memory usage
curl 'http://prometheus:9090/api/v1/query?query=purple_memory_bytes'

# Query queue depth
curl 'http://prometheus:9090/api/v1/query?query=purple_queue_size'
```

#### Grafana Dashboards

- **Main Dashboard** (`purple-main`): Event processing, error rates, latency, queue depth
- **Parser Dashboard** (`purple-parsers`): Per-parser metrics, performance comparison
- Custom dashboards: Create as needed for specific analysis

---

## Scaling Operations

### Horizontal Scaling (Kubernetes)

#### Manual Scaling

```bash
# Scale to N replicas
kubectl scale deployment/purple-parser-eater --replicas=5 -n purple-pipeline

# Verify scaling
kubectl get deployment purple-parser-eater -n purple-pipeline
kubectl get pods -n purple-pipeline
```

#### Auto-scaling Configuration

The HPA (Horizontal Pod Autoscaler) is pre-configured with:
- **Minimum replicas**: 1 (dev), 3 (production)
- **Maximum replicas**: 10
- **Target CPU**: 70%
- **Target Memory**: 80%

To modify HPA:

```bash
# Edit HPA
kubectl edit hpa purple-parser-eater -n purple-pipeline

# Check HPA status
kubectl get hpa purple-parser-eater -n purple-pipeline
kubectl describe hpa purple-parser-eater -n purple-pipeline

# View scaling events
kubectl get events -n purple-pipeline --sort-by='.lastTimestamp' | grep HorizontalPodAutoscaler
```

### Vertical Scaling (Resource Limits)

```bash
# Update resource requests/limits
kubectl set resources deployment purple-parser-eater \
  --requests=cpu=500m,memory=512Mi \
  --limits=cpu=2000m,memory=2Gi \
  -n purple-pipeline

# Verify
kubectl describe deployment purple-parser-eater -n purple-pipeline
```

### VM Scaling (Compute Engine / Auto Scaling Group)

#### AWS Auto Scaling Group

```bash
# Check current capacity
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names purple-pipeline \
  --region us-east-1

# Update desired capacity
aws autoscaling set-desired-capacity \
  --auto-scaling-group-name purple-pipeline \
  --desired-capacity 5 \
  --region us-east-1

# Check scaling activities
aws autoscaling describe-scaling-activities \
  --auto-scaling-group-name purple-pipeline \
  --region us-east-1
```

#### GCP Instance Group Manager

```bash
# Check current size
gcloud compute instance-groups managed describe purple-igm \
  --zone us-central1-a

# Update size
gcloud compute instance-groups managed set-autoscaling purple-igm \
  --max-num-replicas 10 \
  --min-num-replicas 2 \
  --target-cpu-utilization 0.7 \
  --zone us-central1-a

# List instances
gcloud compute instance-groups managed list-instances purple-igm \
  --zone us-central1-a
```

---

## Backup and Recovery

### Database Backups

#### AWS RDS

```bash
# Create manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier purple-pipeline \
  --db-snapshot-identifier purple-backup-$(date +%Y%m%d-%H%M%S)

# List snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier purple-pipeline

# Restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier purple-pipeline-restored \
  --db-snapshot-identifier <snapshot-id>

# Check backup status
aws rds describe-db-instances \
  --db-instance-identifier purple-pipeline \
  --query 'DBInstances[0].{Status:DBInstanceStatus,BackupRetention:BackupRetentionPeriod}'
```

#### GCP Cloud SQL

```bash
# Create backup
gcloud sql backups create purple-backup-$(date +%Y%m%d-%H%M%S) \
  --instance=purple-postgres

# List backups
gcloud sql backups list --instance=purple-postgres

# Restore from backup
gcloud sql backups restore <backup-id> \
  --backup-configuration=default \
  --instance=purple-postgres

# Set up automatic backups (in Terraform)
# Backup configuration in main.tf includes:
# - Daily backups
# - 30-day retention
# - Point-in-time recovery enabled
```

### Configuration Backups

All infrastructure is defined in Terraform and stored in git. To backup configuration:

```bash
# Export Terraform state
terraform state pull > terraform.state.backup

# Store in secure location
gpg --encrypt terraform.state.backup
# or
openssl enc -aes-256-cbc -in terraform.state.backup -out terraform.state.backup.enc

# Backup Kubernetes manifests
kubectl get all -n purple-pipeline -o yaml > k8s-backup.yaml

# Backup database schema
pg_dump -h <db-host> -U purple_app -d purple_pipeline > db-schema-backup.sql
```

### Recovery Procedures

#### Restore from RDS Snapshot

```bash
# 1. Create new instance from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier purple-pipeline-restored \
  --db-snapshot-identifier <snapshot-id>

# 2. Wait for restoration
aws rds wait db-instance-available \
  --db-instance-identifier purple-pipeline-restored

# 3. Update connection string
# Update environment variable: DATABASE_URL

# 4. Verify connection
psql -h <new-db-endpoint> -U purple_app -d purple_pipeline -c "SELECT 1"

# 5. Failover (if hot standby)
# - Update application DNS/load balancer to point to new database
# - Monitor for issues
```

#### Restore from Database Backup

```bash
# 1. Create new database
createdb purple_pipeline_restored -h <db-host> -U postgres

# 2. Restore dump
psql -h <db-host> -U purple_app -d purple_pipeline_restored < db-schema-backup.sql

# 3. Verify
psql -h <db-host> -U purple_app -d purple_pipeline_restored -c "SELECT COUNT(*) FROM events;"
```

#### Recover Kubernetes Cluster

```bash
# 1. If cluster is completely down, redeploy from Terraform
cd deployment/k8s/terraform
terraform apply

# 2. Deploy application
kubectl apply -f deployment/k8s/overlays/production

# 3. Restore persistent data from backup
kubectl create configmap app-backup --from-file=backup-data/
kubectl apply -f restore-pvc.yaml

# 4. Verify
kubectl get all -n purple-pipeline
```

---

## Troubleshooting

### Common Issues

#### Application Crashes/Restarts

```bash
# Check pod restart count
kubectl get pods -n purple-pipeline -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[0].restartCount}{"\n"}{end}'

# Check recent crashes
kubectl describe pod <pod-name> -n purple-pipeline

# Check logs before crash
kubectl logs <pod-name> --previous -n purple-pipeline

# Check for OOM kills
kubectl get events -n purple-pipeline | grep OOM

# Increase resource limits if needed
kubectl set resources deployment purple-parser-eater \
  --limits=memory=2Gi \
  -n purple-pipeline
```

#### Database Connection Issues

```bash
# Test database connectivity
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- \
  psql -h <db-host> -U purple_app -d purple_pipeline -c "SELECT 1"

# Check database status
aws rds describe-db-instances --db-instance-identifier purple-pipeline \
  --query 'DBInstances[0].DBInstanceStatus'

# Check connection from pod
kubectl exec -it <pod-name> -n purple-pipeline -- \
  python3 -c "import psycopg2; conn = psycopg2.connect('host=<db-host> user=purple_app'); print('OK')"

# Check RDS security groups
aws ec2 describe-security-groups --group-ids <sg-id>

# Check RDS subnet groups
aws rds describe-db-subnet-groups --db-subnet-group-name <subnet-group>
```

#### Memory Leaks

```bash
# Monitor memory over time
kubectl top pods -n purple-pipeline --containers

# Check for increasing memory
for i in {1..10}; do
  kubectl top pod <pod-name> -n purple-pipeline
  sleep 60
done

# Restart deployment (rolling restart)
kubectl rollout restart deployment/purple-parser-eater -n purple-pipeline

# Check for process memory leaks
kubectl exec -it <pod-name> -n purple-pipeline -- ps aux | grep python
```

#### High CPU Usage

```bash
# Check CPU metrics
kubectl top pods -n purple-pipeline --sort-by=cpu

# Check individual pod CPU
kubectl describe pod <pod-name> -n purple-pipeline

# Profile application
kubectl exec -it <pod-name> -n purple-pipeline -- python3 -m cProfile -s cumtime /app/main.py

# Check for hot loops
kubectl logs <pod-name> -n purple-pipeline | tail -100
```

#### Network Connectivity

```bash
# Test DNS
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup google.com

# Test external connectivity
kubectl run -it --rm debug --image=busybox --restart=Never -- wget -O- http://www.google.com

# Check network policies
kubectl get networkpolicies -n purple-pipeline
kubectl describe networkpolicy purple-parser-eater -n purple-pipeline

# Test specific service
kubectl run -it --rm debug --image=busybox --restart=Never -- nc -v <service-name> 8080
```

---

## Incident Response

### Incident Response Procedure

1. **Initial Response (First 5 Minutes)**
   - Alert on-call engineer (if not already)
   - Confirm incident (is service actually down?)
   - Notify stakeholders
   - Page escalation contact if P1

2. **Diagnosis (5-15 Minutes)**
   - Check application health endpoint
   - Review recent changes (git log, deployments)
   - Check monitoring dashboards (Grafana, CloudWatch)
   - Check error logs

3. **Immediate Mitigation (15-30 Minutes)**
   - Can we roll back? (If recent change caused it)
   - Can we scale up? (If capacity issue)
   - Can we restart? (If crashed pod)
   - Failover to standby? (If node failure)

4. **Investigation (30+ Minutes)**
   - Root cause analysis
   - Check database health
   - Check upstream services
   - Review metrics before incident

5. **Communication**
   - Update status page every 15 minutes
   - Provide ETA for fix when possible
   - Post-incident: notify all stakeholders

### P1 Incident Checklist

- [ ] Page on-call engineer
- [ ] Create incident ticket
- [ ] Start war room/meeting (if severe)
- [ ] Update status page
- [ ] Attempt immediate mitigation (restart/rollback)
- [ ] Collect logs and metrics
- [ ] Communicate every 15 minutes
- [ ] Post-mortem after resolution

### P2 Incident Checklist

- [ ] Log incident ticket
- [ ] Update status page
- [ ] Investigate during business hours
- [ ] Communicate with affected customers
- [ ] Track for post-mortem

---

## Maintenance Windows

### Planned Maintenance

Schedule maintenance during low-traffic periods (typically Tuesday-Thursday 2-4 AM UTC).

#### Pre-Maintenance Checklist

- [ ] Notify all stakeholders 48 hours in advance
- [ ] Update status page with maintenance window
- [ ] Backup database
- [ ] Backup current configuration
- [ ] Have rollback plan ready
- [ ] Have on-call engineer available
- [ ] Document all changes

#### Database Maintenance

```bash
# Backup first
pg_dump -h <db-host> -U purple_app -d purple_pipeline > backup-before-maintenance.sql

# Perform maintenance
# - Vacuum
# - Analyze
# - Index rebuild
# - Statistics update

# Example:
psql -h <db-host> -U purple_app -d purple_pipeline << EOF
VACUUM ANALYZE;
REINDEX DATABASE purple_pipeline;
EOF

# Verify
psql -h <db-host> -U purple_app -d purple_pipeline -c "SELECT COUNT(*) FROM events;"
```

#### Application Updates

```bash
# 1. Prepare new version
docker build -t gcr.io/project/purple-parser-eater:v1.1.0 .
docker push gcr.io/project/purple-parser-eater:v1.1.0

# 2. Update Kubernetes
kubectl set image deployment/purple-parser-eater \
  purple-parser-eater=gcr.io/project/purple-parser-eater:v1.1.0 \
  -n purple-pipeline

# 3. Monitor rollout
kubectl rollout status deployment/purple-parser-eater -n purple-pipeline

# 4. Run smoke tests
curl -v http://localhost:8080/health

# 5. If issues, rollback
kubectl rollout undo deployment/purple-parser-eater -n purple-pipeline

# 6. Verify rollback
kubectl rollout status deployment/purple-parser-eater -n purple-pipeline
```

#### OS Patching (VMs)

```bash
# For VMs, perform rolling updates
# 1. Remove from load balancer
aws elbv2 deregister-targets --target-group-arn <arn> --targets Id=<instance-id>

# 2. Wait for connections to drain
sleep 60

# 3. Apply patches
sudo apt-get update
sudo apt-get upgrade

# 4. Reboot if kernel updated
sudo reboot

# 5. Wait for service startup
sleep 30

# 6. Verify service
curl http://localhost:8080/health

# 7. Re-register with load balancer
aws elbv2 register-targets --target-group-arn <arn> --targets Id=<instance-id>
```

#### Post-Maintenance Verification

```bash
# 1. Check service health
curl http://<service>/health

# 2. Check metrics
# - Event processing rate
# - Error rate
# - Latency (p95, p99)

# 3. Check logs for errors
kubectl logs deployment/purple-parser-eater -n purple-pipeline

# 4. Run smoke tests
# - Simple event processing
# - All parser types
# - All output sinks

# 5. Monitor for 1 hour
# - CPU/Memory
# - Error rate
# - Any slowdowns
```

---

## Performance Tuning

### Identifying Performance Issues

```bash
# Top slow queries
kubectl logs deployment/purple-parser-eater -n purple-pipeline | grep "duration" | sort -t= -k2 -rn | head -10

# Top error-causing parsers
kubectl logs deployment/purple-parser-eater -n purple-pipeline | grep "error" | cut -d' ' -f3 | sort | uniq -c | sort -rn

# Memory trend
kubectl top pods -n purple-pipeline --containers | tail -1

# Check Prometheus metrics
curl 'http://prometheus:9090/api/v1/query?query=purple_parser_execution_duration_seconds' | jq
```

### Database Performance Tuning

```bash
# Analyze slow queries
psql -h <db-host> -U purple_app -d purple_pipeline << EOF
SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;
EOF

# Enable query logging
ALTER DATABASE purple_pipeline SET log_min_duration_statement = 1000;

# Rebuild indexes
REINDEX TABLE events;
REINDEX TABLE transformations;

# Update statistics
ANALYZE;

# Check index usage
SELECT schemaname, tablename, indexname, idx_scan FROM pg_stat_user_indexes ORDER BY idx_scan;
```

### Application Performance Tuning

```bash
# Increase worker processes
# Edit gunicorn_config.py: workers = 8

# Increase connection pool size
# Edit connection string: max_overflow=20

# Enable caching
# Set CACHE_ENABLED=true

# Monitor cache hit ratio
curl 'http://prometheus:9090/api/v1/query?query=purple:cache:hit_ratio'
```

---

## Post-Incident Review

After any incident, perform a thorough post-mortem:

1. **Timeline**: Document exactly what happened and when
2. **Root Cause**: Why did this happen?
3. **Impact**: How many users affected? How long?
4. **Prevention**: How do we prevent this?
5. **Detection**: How do we detect this faster?
6. **Response**: How do we respond better next time?
7. **Follow-ups**: Action items and owners
8. **Documentation**: Update runbooks/procedures

Create a post-mortem document and share with team within 24 hours.

---

**Last Updated**: 2025-11-08
**Maintained By**: DevOps Team
