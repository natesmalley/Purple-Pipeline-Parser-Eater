# ADR-001: Choice of EKS (Elastic Kubernetes Service) as Primary Deployment Platform

## Status
ACCEPTED

## Date
2025-11-09

## Context

The Purple Pipeline Parser Eater needs a reliable, scalable deployment platform that can support:
- Event processing pipelines with varying load
- High availability and automatic failover
- Easy application updates and rollbacks
- Multi-environment support (development, staging, production)
- Integration with cloud-native services
- Enterprise-grade monitoring and logging

Three primary options were evaluated:

### Option 1: EKS (Elastic Kubernetes Service)
**Pros:**
- Fully managed Kubernetes
- AWS handles control plane management and updates
- Native integration with AWS services (RDS, ElastiCache, MSK)
- Horizontal and vertical auto-scaling
- Load balancing via ALB/NLB
- CloudWatch integration for monitoring
- Industry standard for production deployments
- Multi-region support
- Strong ecosystem (Helm, operators, add-ons)

**Cons:**
- Control plane costs ($0.10/hour)
- Requires Kubernetes knowledge
- Larger initial learning curve
- More moving parts to manage

### Option 2: EC2 (Virtual Machines)
**Pros:**
- Lower baseline costs (no control plane fee)
- Simpler mental model (traditional server management)
- Easier debugging with SSH access
- Less operational complexity initially

**Cons:**
- Manual scaling management
- No automatic rollouts or rollbacks
- Higher operational burden
- More error-prone deployments
- Harder to implement zero-downtime updates
- Difficult to scale horizontally
- Less cloud-native
- Difficult to achieve HA without significant effort
- More infrastructure to manage

### Option 3: ECS (Elastic Container Service)
**Pros:**
- AWS-native container orchestration
- No additional control plane cost (included in EC2/Fargate)
- Integrated with AWS CloudFormation
- Good for simple containerized applications

**Cons:**
- Proprietary (AWS-only)
- Smaller ecosystem than Kubernetes
- Less portable across clouds
- Difficult to migrate to other platforms
- Limited third-party tooling support
- Complex service discovery

### Option 4: Docker Compose / Self-Managed
**Pros:**
- Simple to get started
- No cloud costs for orchestration

**Cons:**
- No production-grade HA
- No automatic scaling
- Difficult to manage updates
- Single point of failure
- No monitoring integration
- Not suitable for enterprise use

## Decision

**EKS was chosen as the primary deployment platform.**

Reasoning:
1. **Operational Excellence**: EKS manages the control plane, freeing the team to focus on application deployment and operations
2. **Scalability**: Horizontal auto-scaling handles variable workloads without manual intervention
3. **Reliability**: Multi-AZ deployment with automatic node replacement ensures high availability
4. **Standards Compliance**: Kubernetes is the industry standard for container orchestration
5. **Portability**: Kubernetes skills are transferable; applications can run on any Kubernetes distribution
6. **Integration**: Native integration with AWS services (RDS, ElastiCache, MSK, CloudWatch)
7. **Ecosystem**: Rich ecosystem of tools, operators, and community support
8. **Enterprise Ready**: Suitable for mission-critical production workloads
9. **Security**: Fine-grained RBAC, network policies, and IAM integration
10. **Cost Optimization**: With proper sizing and spot instances, costs are competitive with other options

## Supporting Infrastructure

To support EKS deployment, the following services are included:

### Data Services
- **RDS PostgreSQL**: Multi-AZ managed database with automated backups
- **ElastiCache Redis**: In-memory caching with automatic failover
- **MSK Kafka**: Managed message queue for event streaming

### Networking
- **VPC with Public/Private Subnets**: Network segmentation for security
- **NAT Gateway**: Secure outbound internet access for private resources
- **ALB/NLB**: Load balancing with TLS termination

### Security
- **Security Groups**: Fine-grained network access control
- **Network Policies**: Kubernetes-native network segmentation
- **KMS Encryption**: Encryption at rest for all data stores
- **IAM Roles**: Fine-grained permission management
- **Secrets Manager**: Secure credential storage

### Observability
- **CloudWatch**: AWS native metrics and logs
- **Prometheus**: Kubernetes-native metrics collection
- **Grafana**: Visualization dashboards

## Alternatives Provided

While EKS is the primary choice, the deployment infrastructure includes alternatives:

1. **VM Deployment** (deployment/vm/deploy.sh): For single-server deployments or edge cases
2. **GCP Option** (deployment/gcp/terraform): For organizations with GCP preference
3. **Self-Managed Kubernetes**: For organizations with Kubernetes expertise and cost constraints

These alternatives ensure flexibility while maintaining EKS as the recommended path.

## Implications

### Positive
- Highly scalable, fault-tolerant production environment
- Aligned with industry best practices
- Team can leverage Kubernetes skills across multiple organizations
- Strong support and community resources
- Easier hiring of Kubernetes-experienced engineers

### Negative
- Higher operational complexity than simple VMs
- Control plane costs (~$0.10/hour = ~$73/month)
- Requires ongoing Kubernetes cluster management
- More resources needed for HA setup

## Related ADRs
- ADR-002: Multi-AZ Deployment Strategy
- ADR-003: Separation of Databases from Kubernetes
- ADR-004: Infrastructure as Code with Terraform

## Further Reading

1. AWS EKS Best Practices Guide: https://aws.github.io/aws-eks-best-practices/
2. Kubernetes Documentation: https://kubernetes.io/docs/
3. CNCF Landscape: https://landscape.cncf.io/
4. AWS Well-Architected Framework: https://aws.amazon.com/architecture/well-architected/

## Appendix: Cost Comparison (Monthly)

| Component | EKS | EC2 | ECS |
|-----------|-----|-----|-----|
| Control Plane | $73 | $0 | $0 |
| 3x t3.large Nodes | $150 | $150 | $150 |
| RDS db.t3.small | $50 | $50 | $50 |
| ElastiCache t3.micro | $20 | $20 | $20 |
| MSK 3x m5.large | $300 | N/A | N/A |
| ALB | $20 | $20 | $20 |
| **Total** | **$613** | **$240** | **$240** |

Note: EKS control plane cost is offset by reduced operational overhead and better resource utilization through auto-scaling.

