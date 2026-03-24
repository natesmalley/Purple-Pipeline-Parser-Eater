# ADR-003: Separation of Databases from Kubernetes Cluster

## Status
ACCEPTED

## Date
2025-11-09

## Context

Purple Pipeline Parser Eater needs persistent data storage for:
- Event data and processing state
- Application configuration
- User authentication and authorization
- Session data
- Cache/session store

Two architectural approaches were evaluated:

### Key Question
Should databases run inside the Kubernetes cluster or as external managed services?

## Options Evaluated

### Option 1: Databases Inside Kubernetes (Not Chosen)

**Using StatefulSets for PostgreSQL and Redis:**

**Pros:**
- Single infrastructure to manage (Kubernetes)
- Can use volumes for persistence
- Standard Kubernetes patterns

**Cons:**
- **Operational complexity**: Managing stateful workloads in Kubernetes is complex
- **High availability burden**: Must implement custom replication, failover
- **Backup complexity**: Need additional tools and scripts
- **Performance**: Shared compute resources with application workloads
- **Resource conflicts**: Database resource usage competes with applications
- **Expertise required**: Specialized Kubernetes operator knowledge needed
- **Upgrade risks**: Database upgrades block cluster upgrades
- **Disaster recovery**: Complex backup and recovery procedures
- **Not recommended**: Kubernetes community recommends external databases for production

**Industry Best Practice**: "Don't run stateful workloads in Kubernetes unless you're an expert"

### Option 2: External Managed Services (Chosen)

**Using AWS RDS, ElastiCache, MSK:**

**Pros:**
- **AWS manages HA**: Automatic failover, backups, patches
- **Lower operational burden**: Focus on applications, not infrastructure
- **Better performance**: Dedicated hardware, no resource contention
- **Enterprise features**: Automated backups, point-in-time recovery, encryption
- **Simpler upgrades**: Database upgrades independent of cluster
- **Disaster recovery**: AWS-managed backup and recovery
- **Cost effective**: Economies of scale from AWS
- **Security**: AWS-managed security patches
- **SLA guarantees**: AWS provides 99.95% uptime SLA
- **Monitoring**: Deep integration with CloudWatch

**Cons:**
- Data in separate cloud services (acceptable trade-off)
- Network latency (minimal, < 1ms within AZ)
- Slightly higher cost than self-managed (offset by reduced ops burden)
- Vendor lock-in to AWS (acceptable for this use case)

## Decision

**Databases are provided as external managed AWS services:**
- **RDS PostgreSQL** for transactional data
- **ElastiCache Redis** for caching and session storage
- **MSK Kafka** for event streaming and message queues

### Rationale

1. **AWS Responsibility Model**
   - AWS manages: infrastructure, HA, backups, patches, security
   - Team manages: application, schema, queries, data optimization

2. **Operational Excellence**
   - Automatic failover with < 2 minute RTO
   - Zero-touch patching
   - Point-in-time recovery capability
   - Automated backups across AZs

3. **Reliability**
   - Multi-AZ deployment with automatic standby replica
   - Synchronous replication to ensure zero data loss
   - AWS manages read replicas for scaling
   - Health checks integrated into cluster operations

4. **Security**
   - Encryption at rest (KMS)
   - Encryption in transit (TLS/SSL)
   - Private subnet deployment (no internet access)
   - IAM-based access control
   - Audit logging in CloudTrail

5. **Performance**
   - Dedicated resources for databases
   - No resource contention with applications
   - AWS-optimized performance settings
   - Read replicas for scaling read-heavy workloads

6. **Cost**
   - Managed service economies of scale
   - Reduced operational overhead
   - Better resource utilization
   - Pay-as-you-go pricing

## Architecture

### Network Topology

```
┌────────────────────────────────────────────────┐
│             AWS VPC                            │
├────────────────────────────────────────────────┤
│                                                │
│  ┌──────────────────────────────────────────┐ │
│  │  EKS Kubernetes Cluster                  │ │
│  │  (Public/Private Subnets)                │ │
│  │                                          │ │
│  │  ┌──────────────────────────────────┐   │ │
│  │  │ Pods running Purple Pipeline     │   │ │
│  │  │ - Uses cluster DNS for discovery │   │ │
│  │  └──────────────────────────────────┘   │ │
│  │             │         │         │        │ │
│  └─────────────┼─────────┼─────────┼────────┘ │
│                │         │         │          │
│  ┌─────────────▼──┐  ┌───▼───────┐ ┌────▼──┐ │
│  │   RDS          │  │ ElastiCache│ │ MSK   │ │
│  │ PostgreSQL     │  │   Redis    │ │ Kafka │ │
│  │ (Private       │  │ (Private   │ │       │ │
│  │  Subnets)      │  │  Subnets)  │ │       │ │
│  │                │  │            │ │       │ │
│  │ Multi-AZ      │  │ Multi-AZ   │ │Multi- │ │
│  │ Failover      │  │ Failover   │ │AZ     │ │
│  │ Encryption    │  │ Encryption │ │TLS    │ │
│  └────────────────┘  └────────────┘ └───────┘ │
│                                                │
└────────────────────────────────────────────────┘
```

### Communication Flow

1. **Kubernetes to RDS**
   - DNS: postgres.c3yqy3y.us-east-1.rds.amazonaws.com
   - Port: 5432 (PostgreSQL)
   - Security: Inbound rule allows port 5432 from EKS security group
   - Encryption: TLS required for connections

2. **Kubernetes to ElastiCache**
   - DNS: redis-cache.abc123.cache.amazonaws.com
   - Port: 6379 (Redis)
   - Auth: Redis AUTH token from AWS Secrets Manager
   - Encryption: TLS encryption enabled

3. **Kubernetes to MSK**
   - Bootstrap: `b-1.kafka.us-east-1.msk.amazonaws.com:9092`
   - SASL/TLS authentication
   - VPC endpoints for private access

## Data Flow Architecture

```
┌──────────────────┐
│  Event Sources   │
│  (API, Files,    │
│   Webhooks)      │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────┐
│  Kubernetes Service          │
│  - Event Ingestion Pod       │
│  - Processing Pods           │
│  - Output Pods               │
└──────────────────────────────┘
         │     │     │
         │     │     │
    ┌────▼─ ──▼─ ──▼────┐
    │ Redis │RDS│ MSK    │
    │ Cache │DB │ Queue  │
    └────────────────────┘
         │     │     │
         │     │     │
    ┌────▼─────▼─────▼───┐
│ Output Adapters    │
│ - S3               │
│ - Webhook Delivery │
│ - Streaming        │
└────────────────────┘
```

## Implementation Details

### PostgreSQL (RDS)

```hcl
# RDS Configuration
resource "aws_db_instance" "postgres" {
  identifier          = "purple-pipeline-db"
  engine              = "postgres"
  engine_version      = "15.2"
  instance_class      = "db.t3.small"
  allocated_storage   = 100
  storage_encrypted   = true
  kms_key_id         = aws_kms_key.rds.arn

  # High Availability
  multi_az           = true
  backup_retention_period = 30

  # Security
  publicly_accessible = false
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name = aws_db_subnet_group.rds.name

  # Network
  skip_final_snapshot = false
  final_snapshot_identifier = "purple-pipeline-final-${timestamp()}"
}
```

### ElastiCache (Redis)

```hcl
# Redis Configuration
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "purple-pipeline-cache"
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 3

  # High Availability
  automatic_failover_enabled = true
  multi_az_enabled          = true

  # Security
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token_enabled        = true

  # Network
  security_group_ids = [aws_security_group.elasticache.id]
  subnet_group_name  = aws_elasticache_subnet_group.redis.name
}
```

### MSK (Kafka)

```hcl
# Kafka Configuration
resource "aws_msk_cluster" "kafka" {
  cluster_name           = "purple-pipeline-kafka"
  kafka_version          = "3.5.1"
  number_of_broker_nodes = 3
  broker_node_group_info {
    instance_type   = "kafka.m5.large"
    ebs_volume_size = 100

    # Network
    security_groups  = [aws_security_group.kafka.id]
    subnet_ids       = aws_subnet.private[*].id
  }

  # Security
  encryption_info {
    encryption_in_transit {
      enabled = true
    }
    encryption_at_rest {
      enabled = true
      kms_key_arn = aws_kms_key.kafka.arn
    }
  }
}
```

## Application Configuration

### Environment Variables

Applications running in Kubernetes receive database credentials via:

```yaml
# ConfigMap for non-sensitive configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: database-config
data:
  DB_HOST: "postgres.c3yqy3y.us-east-1.rds.amazonaws.com"
  DB_PORT: "5432"
  DB_NAME: "purple_pipeline"
  REDIS_HOST: "redis-cache.abc123.cache.amazonaws.com"
  REDIS_PORT: "6379"
  KAFKA_BROKERS: "b-1.kafka.us-east-1.msk.amazonaws.com:9092"

---
# Secrets for sensitive data
apiVersion: v1
kind: Secret
metadata:
  name: database-secrets
type: Opaque
stringData:
  DB_USER: "postgres"
  DB_PASSWORD: <from AWS Secrets Manager>
  REDIS_AUTH: <from AWS Secrets Manager>
```

## Disaster Recovery

### Backup Strategy
- **RDS**: Automated daily backups, 30-day retention, cross-AZ
- **ElastiCache**: Snapshots to S3 daily
- **MSK**: Data replicated across brokers, topic retention policies

### Recovery Procedures
1. **RDS Database Loss**
   - Restore from latest snapshot (< 1 hour recovery)
   - Or use point-in-time recovery (any point in past 30 days)

2. **ElastiCache Loss**
   - Create new cluster from snapshot (< 10 minutes)
   - Automatic failover for node failures (< 1 minute)

3. **MSK Topic Loss**
   - Data in other broker replicas (default replication factor: 3)
   - Topic retention policy determines data availability

### Testing
- Monthly: Test RDS restore from snapshot
- Monthly: Test ElastiCache snapshot restore
- Quarterly: Full disaster recovery drill

## Monitoring and Operations

### CloudWatch Metrics
- RDS: CPU, connections, disk space, replication lag
- ElastiCache: Evictions, memory usage, hit rate
- MSK: Broker CPU, network throughput, lag

### Alarms
- RDS: High CPU (>80%), low disk space (<10%), connection issues
- ElastiCache: High evictions, replication issues
- MSK: Broker down, high under-replicated partitions

### Maintenance
- RDS: AWS handles patches during maintenance window (mon 03:00-04:00 UTC)
- ElastiCache: Rolling patches (one node at a time)
- MSK: Broker replacement during maintenance window

## Cost Analysis

### Monthly Costs
- RDS db.t3.small: ~$50
- ElastiCache cache.t3.micro: ~$20
- MSK 3x m5.large: ~$300
- **Total: ~$370/month**

### Cost Justification
- Eliminates need for DBA infrastructure
- Automatic backups included
- High availability included
- Security patches included
- Monitoring integration included
- ~$2000/month of operational overhead savings vs self-managed

## Migration Path

If requirements change, migration is possible:
1. **To self-managed**: Export data via RDS snapshots
2. **To DMS service**: AWS Database Migration Service available
3. **To other clouds**: Standard PostgreSQL/Redis tools available

## Related ADRs
- ADR-001: Choice of EKS
- ADR-002: Multi-AZ Deployment
- ADR-004: Security Architecture

## Further Reading
1. AWS RDS Best Practices: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html
2. EKS + RDS Integration: https://aws.amazon.com/blogs/kubernetes/using-amazon-rds-with-eks/
3. Kubernetes External Database Pattern: https://kubernetes.io/docs/concepts/configuration/secret/
4. Database Reliability Engineering: https://www.oreilly.com/library/view/database-reliability-engineering/9781491925935/

