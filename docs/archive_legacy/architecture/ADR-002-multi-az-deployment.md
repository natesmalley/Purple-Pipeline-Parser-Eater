# ADR-002: Multi-Availability Zone (Multi-AZ) Deployment Strategy

## Status
ACCEPTED

## Date
2025-11-09

## Context

The Purple Pipeline Parser Eater must meet production-grade availability requirements:
- Minimize downtime during AWS infrastructure maintenance
- Survive single availability zone (AZ) failure
- Support zero-downtime deployments
- Meet enterprise SLA requirements (typically 99.95% uptime)

AWS provides multiple availability zones within each region, offering geographic isolation and independent infrastructure.

## Options Evaluated

### Option 1: Single AZ Deployment
**Characteristics:**
- All resources in one availability zone
- Lower operational complexity
- Reduced data transfer costs (no cross-AZ charges)

**Risks:**
- Vulnerable to AZ-level outages (AWS maintenance, equipment failure)
- AWS explicitly recommends against this for production
- Cannot achieve HA
- Difficult to perform maintenance without downtime

**Not Recommended for Production**

### Option 2: Multi-AZ Deployment (Chosen)
**Characteristics:**
- Resources distributed across 3 availability zones
- Automatic failover for managed services
- Load balancing between AZs
- No single point of failure

**Benefits:**
- Highest availability (AWS SLA: 99.99% uptime)
- Automatic failover for RDS, ElastiCache
- Network segmentation for security
- Proven in production environments

**Tradeoffs:**
- Slightly higher costs due to multiple NAT gateways and load balancing
- Minor cross-AZ data transfer costs (~$0.01/GB)
- More operational complexity

### Option 3: Multi-Region Deployment
**Characteristics:**
- Resources in multiple AWS regions
- Can survive entire region failure

**Not Selected Because:**
- Significantly higher costs
- Complex synchronization requirements
- Overkill for typical use cases
- Reserved for disaster recovery (optional future phase)

## Decision

**Multi-AZ deployment across 3 availability zones is the standard approach.**

### Specific Implementation

#### Kubernetes Cluster (EKS)
- **3 availability zones** (automatic in each region)
- Nodes distributed: 1 node per AZ minimum
- Pod anti-affinity rules distribute workloads across nodes
- Application services span all AZs via Kubernetes DNS

#### Databases (RDS PostgreSQL)
- **Multi-AZ enabled** (primary + standby replica)
- Automatic failover in case of AZ outage (< 2 minutes)
- Synchronous replication to standby
- Backup stored in separate AZ

#### Cache (ElastiCache Redis)
- **Multi-AZ cluster mode enabled**
- Automatic failover for node replacement
- Data replicated across AZs

#### Load Balancer (ALB)
- **Deployed in all AZs**
- Health checks route traffic away from failed AZs
- Cross-zone load balancing enabled

#### NAT Gateways
- **One per AZ** for redundant outbound internet access
- Each in own public subnet for isolation
- Route tables direct private subnets to local AZ NAT gateway

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        AWS Region                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┬──────────────┬──────────────┐              │
│  │    AZ-1     │    AZ-2      │    AZ-3      │              │
│  ├─────────────┼──────────────┼──────────────┤              │
│  │             │              │              │              │
│  │ ┌─────────┐ │ ┌──────────┐ │ ┌──────────┐ │              │
│  │ │ Public  │ │ │ Public   │ │ │ Public   │ │              │
│  │ │ Subnet  │ │ │ Subnet   │ │ │ Subnet   │ │              │
│  │ │ 10.0.1  │ │ │ 10.0.2   │ │ │ 10.0.3   │ │              │
│  │ └────┬────┘ │ └────┬─────┘ │ └────┬─────┘ │              │
│  │      │      │      │       │      │       │              │
│  │ ┌────▼────┐ │ ┌────▼─────┐ │ ┌────▼─────┐ │              │
│  │ │   NAT   │ │ │   NAT    │ │ │   NAT    │ │              │
│  │ │Gateway  │ │ │ Gateway  │ │ │ Gateway  │ │              │
│  │ └────┬────┘ │ └────┬─────┘ │ └────┬─────┘ │              │
│  │      │      │      │       │      │       │              │
│  │ ┌────▼──────────────▼───────────────▼────┐ │              │
│  │ │     Kubernetes Cluster (EKS)           │ │              │
│  │ │  - Nodes distributed across AZs        │ │              │
│  │ │  - Pods spread via anti-affinity       │ │              │
│  │ └────────────────────────────────────────┘ │              │
│  │      │      │      │       │      │       │              │
│  │ ┌────▼────┐ │      │       │      │       │              │
│  │ │Private  │ │ ┌────▼─────┐ │ ┌────▼─────┐│              │
│  │ │ Subnet  │ │ │ Private  │ │ │ Private  ││              │
│  │ │ 10.0.11 │ │ │ Subnet   │ │ │ Subnet   ││              │
│  │ └────┬────┘ │ │ 10.0.12  │ │ │ 10.0.13  ││              │
│  │      │      │ └────┬─────┘ │ └────┬─────┘│              │
│  │      │      │      │       │      │       │              │
│  │ ┌────▼──────────────▼───────────────▼────┐ │              │
│  │ │      RDS Database (Multi-AZ)           │ │              │
│  │ │  - Primary in AZ-1                     │ │              │
│  │ │  - Standby in AZ-2                     │ │              │
│  │ │  - Automated failover enabled          │ │              │
│  │ └────────────────────────────────────────┘ │              │
│  │                                             │              │
│  │ ┌──────────────────────────────────────────┐│              │
│  │ │  ElastiCache Redis (Multi-AZ)            ││              │
│  │ │  - Replica sets across AZs               ││              │
│  │ └──────────────────────────────────────────┘│              │
│  │                                             │              │
│  │ ┌──────────────────────────────────────────┐│              │
│  │ │  MSK Kafka (Multi-AZ)                    ││              │
│  │ │  - Brokers: 1 per AZ (3 total)           ││              │
│  │ └──────────────────────────────────────────┘│              │
│  │                                             │              │
│  └─────────────────────────────────────────────┘              │
│                        ▲                                      │
│                        │                                      │
│                   ┌────▼──────┐                               │
│                   │    ALB    │                               │
│                   │ Multi-AZ  │                               │
│                   └────┬──────┘                               │
│                        │                                      │
└────────────────────────┼──────────────────────────────────────┘
                         │
                   Internet Traffic
```

## Subnet Distribution

```
VPC CIDR: 10.0.0.0/16

Public Subnets (for NAT Gateway and ALB):
  AZ-1: 10.0.1.0/24   (256 IPs)
  AZ-2: 10.0.2.0/24   (256 IPs)
  AZ-3: 10.0.3.0/24   (256 IPs)

Private Subnets (for Kubernetes, RDS, ElastiCache):
  AZ-1: 10.0.11.0/24  (256 IPs)
  AZ-2: 10.0.12.0/24  (256 IPs)
  AZ-3: 10.0.13.0/24  (256 IPs)

Database Subnets:
  AZ-1: 10.0.21.0/24  (256 IPs)
  AZ-2: 10.0.22.0/24  (256 IPs)
  AZ-3: 10.0.23.0/24  (256 IPs)

Cache Subnets:
  AZ-1: 10.0.31.0/24  (256 IPs)
  AZ-2: 10.0.32.0/24  (256 IPs)
  AZ-3: 10.0.33.0/24  (256 IPs)
```

## High Availability Guarantees

### RTO and RPO (Recovery objectives)

| Component | RTO | RPO | Notes |
|-----------|-----|-----|-------|
| EKS Nodes | 5 min | 0 | Auto-replace failed nodes |
| RDS Primary | 2 min | 0 | Automatic failover to standby |
| ElastiCache | 1 min | 0 | Automatic node replacement |
| ALB | <1 min | N/A | Traffic reroutes automatically |
| MSK Broker | 5 min | 0 | New broker starts automatically |

### AWS Maintenance Windows

Multi-AZ deployment allows AWS to perform maintenance on one AZ while others remain operational:
- Typical maintenance windows: 30 minutes per month
- Backup window: 6 hours (never impacts production)
- Patch application: Rolling updates (one AZ at a time)

## Cost Implications

**Additional monthly costs for Multi-AZ:**
- Extra NAT Gateways: 2 × $32 = $64
- RDS Multi-AZ fee: +50% (included in on-demand pricing)
- Cross-AZ data transfer: ~$5-10 (negligible)
- **Total additional: ~$70-75/month (~12% increase)**

**Justification:**
- Eliminates single points of failure
- Enables zero-downtime updates
- Meets enterprise SLA requirements
- Cost is minimal compared to downtime costs

## Scaling Considerations

### Horizontal Scaling
Multi-AZ design simplifies horizontal scaling:
- Add new nodes in any AZ
- EKS automatically manages distribution
- Load balancer automatically includes new nodes

### Vertical Scaling
- Can increase instance size during maintenance window
- RDS can be scaled with brief downtime
- ElastiCache can be scaled without downtime

## Operations Implications

### Health Monitoring
- Monitor each AZ independently
- Set up AZ-specific alarms
- Watch cross-AZ latency

### Deployment Strategy
- Rolling deployments naturally span AZs
- Ensure pod affinity rules don't concentrate workloads
- Use pod disruption budgets to ensure availability

### Backup Strategy
- RDS automated backups span AZs
- S3 replication to another region recommended
- Database snapshots automatically cross-AZ

## Related ADRs
- ADR-001: Choice of EKS
- ADR-003: Separation of Databases
- ADR-005: Infrastructure as Code with Terraform

## Further Reading
1. AWS Availability Zones: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-regions-availability-zones.html
2. RDS Multi-AZ: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html
3. EKS High Availability: https://aws.github.io/aws-eks-best-practices/reliability/
4. Kubernetes Pod Affinity: https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#affinity-and-anti-affinity

