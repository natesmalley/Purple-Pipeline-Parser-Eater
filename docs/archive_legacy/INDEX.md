# Documentation Index
## Purple Pipeline Parser Eater v9.0.0

**Last Updated**: 2025-11-09
**Project Status**: 100% FedRAMP High Compliant

---

> Harness Lean Mode: treat Kubernetes/platform-deployment docs as archival/reference material unless a milestone explicitly requires infrastructure work.

## Quick Start (Start Here!)

- **[START_HERE.md](START_HERE.md)** - Project overview and getting started guide
- **[WHAT_YOU_ACTUALLY_NEED.md](WHAT_YOU_ACTUALLY_NEED.md)** - Essential files and concepts
- **[SECURITY-COMPLIANCE-SUMMARY.md](../SECURITY-COMPLIANCE-SUMMARY.md)** - Security status and roadmap

---

## FedRAMP High Compliance

### Current Status
- **[SECURITY-COMPLIANCE-SUMMARY.md](../SECURITY-COMPLIANCE-SUMMARY.md)** - Executive compliance summary
- **[FEDRAMP-COMPLIANCE-AUDIT.md](FEDRAMP-COMPLIANCE-AUDIT.md)** - Complete security audit (2000+ lines)
- **[FEDRAMP-REMEDIATION-GUIDE.md](FEDRAMP-REMEDIATION-GUIDE.md)** - Step-by-step remediation guide

### Compliance Frameworks
- **[STIG_COMPLIANCE_MATRIX.md](STIG_COMPLIANCE_MATRIX.md)** - STIG requirements mapping
- **[FIPS_140-2_ATTESTATION.md](FIPS_140-2_ATTESTATION.md)** - FIPS 140-2 compliance
- **[SYSTEM_SECURITY_PLAN.md](SYSTEM_SECURITY_PLAN.md)** - Security documentation

---

## Remediation Agent Documentation

> **Note**: Agent prompt files are stored privately in `.local/agent-prompts-private/` and are NOT synced to GitHub. This protects internal execution instructions from public exposure.

### Agent 1: Secrets Management & State Encryption
- **REMEDIATION-AGENT-1-PROMPT.md** *(Private - `.local/agent-prompts-private/`)* - Complete deployment guide (3500+ lines)
- 8 detailed tasks covering:
  - AWS Secrets Manager setup
  - Automatic password rotation
  - Remote encrypted Terraform state
  - DynamoDB state locking

### Agent 2: Audit Logging & Threat Detection
- **REMEDIATION-AGENT-2-PROMPT.md** *(Private - `.local/agent-prompts-private/`)* - Complete deployment guide (3500+ lines)
- **[REMEDIATION-AGENT-2-COMPLETION-REPORT.md](REMEDIATION-AGENT-2-COMPLETION-REPORT.md)** - Execution results and validation
- **[REMEDIATION-AGENT-2-IMPLEMENTATION-SUMMARY.md](REMEDIATION-AGENT-2-IMPLEMENTATION-SUMMARY.md)** - Architecture overview
- **[REMEDIATION-AGENT-2-DEPLOYMENT-GUIDE.md](REMEDIATION-AGENT-2-DEPLOYMENT-GUIDE.md)** - Detailed deployment steps
- 8 detailed tasks covering:
  - CloudTrail multi-region logging
  - AWS Config compliance monitoring
  - GuardDuty threat detection
  - VPC Flow Logs
  - EventBridge alerting

### Agent 3: TLS/HTTPS & IAM Hardening
- **REMEDIATION-AGENT-3-PROMPT.md** *(Private - `.local/agent-prompts-private/`)* - Complete deployment guide (3500+ lines)
- **[REMEDIATION-AGENT-3-COMPLETION-REPORT.md](REMEDIATION-AGENT-3-COMPLETION-REPORT.md)** - Execution results and validation
- 8 detailed tasks covering:
  - ACM certificate management
  - Load balancer with HTTPS
  - IAM hardening (least privilege)
  - Network security (3-layer defense)
  - Kubernetes network policies

### Accessing Private Agent Prompts

Agent prompt files are stored locally for security reasons. To access them:
```
.local/agent-prompts-private/
├── REMEDIATION-AGENT-1-PROMPT.md
├── REMEDIATION-AGENT-2-PROMPT.md
└── REMEDIATION-AGENT-3-PROMPT.md
```

These files contain detailed internal execution instructions and are excluded from GitHub synchronization via `.gitignore`. They are available locally for:
- Internal agent execution and reference
- Local testing and validation
- Security-sensitive operations documentation

---

## Infrastructure & Deployment

### Architecture Documentation
- **[architecture/ADR-001-eks-platform-choice.md](architecture/ADR-001-eks-platform-choice.md)** - EKS platform decision
- **[architecture/ADR-002-multi-az-deployment.md](architecture/ADR-002-multi-az-deployment.md)** - Multi-AZ strategy
- **[architecture/ADR-003-databases-outside-kubernetes.md](architecture/ADR-003-databases-outside-kubernetes.md)** - Database architecture
- **[architecture/ADR-004-infrastructure-as-code-terraform.md](architecture/ADR-004-infrastructure-as-code-terraform.md)** - IaC approach

### Deployment Guides
- **[deployment/PRODUCTION_DEPLOYMENT_GUIDE.md](deployment/PRODUCTION_DEPLOYMENT_GUIDE.md)** - Production deployment steps
- **[deployment/DOCKER_DEPLOYMENT_GUIDE.md](deployment/DOCKER_DEPLOYMENT_GUIDE.md)** - Docker deployment
- **[deployment/DOCKER_TESTING_PLAN.md](deployment/DOCKER_TESTING_PLAN.md)** - Docker testing
- **[COMPLETE_DEPLOYMENT_GUIDE.md](COMPLETE_DEPLOYMENT_GUIDE.md)** - Comprehensive guide

### Setup & Configuration
- **[SETUP_ENVIRONMENT_VARIABLES.md](SETUP_ENVIRONMENT_VARIABLES.md)** - Environment variable setup
- **[DATAPLANE_BINARY_SETUP.md](DATAPLANE_BINARY_SETUP.md)** - Dataplane binary setup
- **[QUICK_START_FINAL_SETUP.md](QUICK_START_FINAL_SETUP.md)** - 5-minute quick start
- **[TERRAFORM_BEST_PRACTICES.md](TERRAFORM_BEST_PRACTICES.md)** - IaC best practices

---

## Security & Compliance

### Security Documentation
- **[SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md)** - Security design overview
- **[SECURITY_INCIDENT_RESPONSE_PLAN.md](SECURITY_INCIDENT_RESPONSE_PLAN.md)** - Incident response procedures
- **[THREAT_MODEL.md](THREAT_MODEL.md)** - Threat modeling
- **[SECURITY_REVIEW_CHECKLIST.md](SECURITY_REVIEW_CHECKLIST.md)** - Security review checklist

### Security Folders
- **[security/](security/)** - Detailed security documentation
  - AWS security hardening guides
  - Vulnerability remediation plans
  - Security audit reports
  - CSRF and validation analysis

---

## Testing & Validation

### Testing Documentation
- **[TESTING_AGENT_1_PROMPT.md](TESTING_AGENT_1_PROMPT.md)** - Agent 1 testing guide
- **[TESTING_AGENT_2_PROMPT.md](TESTING_AGENT_2_PROMPT.md)** - Agent 2 testing guide
- **[TESTING_AGENT_3_PROMPT.md](TESTING_AGENT_3_PROMPT.md)** - Agent 3 testing guide
- **[TEST_COVERAGE_GAPS_ANALYSIS.md](TEST_COVERAGE_GAPS_ANALYSIS.md)** - Test coverage analysis
- **[VALIDATION_AND_TESTING_REPORT.md](VALIDATION_AND_TESTING_REPORT.md)** - Test results

### Verification Documentation
- **[verification/](verification/)** - Verification procedures
  - Agent implementation verification
  - Event pipeline verification
  - Verification summary

---

## Operational Documentation

### Runbooks & Operations
- **[OPERATIONAL_RUNBOOKS.md](OPERATIONAL_RUNBOOKS.md)** - Operational procedures
- **[SECURITY_RUNBOOKS.md](SECURITY_RUNBOOKS.md)** - Security procedures
- **[DATA_FLOW_DIAGRAMS.md](DATA_FLOW_DIAGRAMS.md)** - Data flow documentation

### Monitoring & Observability
- **[MONITORING_TESTING_ARCHITECTURE.md](MONITORING_TESTING_ARCHITECTURE.md)** - Monitoring design
- **[DEPLOYMENT_READINESS_REPORT.md](DEPLOYMENT_READINESS_REPORT.md)** - Readiness assessment

---

## Agent Documentation (Legacy)

### Event Ingestion (Agent 1)
- **[agent-prompts/AGENT_1_EVENT_INGESTION_PROMPT.md](agent-prompts/AGENT_1_EVENT_INGESTION_PROMPT.md)**
- **[AGENT_2_RUNTIME_SERVICE_ARCHITECTURE.md](AGENT_2_RUNTIME_SERVICE_ARCHITECTURE.md)**

### Transform Pipeline (Agent 2)
- **[agent-prompts/AGENT_2_TRANSFORM_PIPELINE_PROMPT.md](agent-prompts/AGENT_2_TRANSFORM_PIPELINE_PROMPT.md)**
- **[AGENT_3_IMPLEMENTATION_SUMMARY.md](AGENT_3_IMPLEMENTATION_SUMMARY.md)**

### Output Service (Agent 3)
- **[agent-prompts/AGENT_3_OBSERVO_OUTPUT_PROMPT.md](agent-prompts/AGENT_3_OBSERVO_OUTPUT_PROMPT.md)**
- **[OUTPUT_SERVICE_ARCHITECTURE.md](OUTPUT_SERVICE_ARCHITECTURE.md)**

---

## Demonstrations & Examples

### Demo Documentation
- **[demos/10_PARSER_DEMO_GUIDE.md](demos/10_PARSER_DEMO_GUIDE.md)** - 10-parser demo guide
- **[demos/DEMO_QUICK_REF.md](demos/DEMO_QUICK_REF.md)** - Quick reference
- **[HONEST_TESTING_STRATEGY.md](HONEST_TESTING_STRATEGY.md)** - Testing approach

---

## Historical Documentation

**Location**: [historical/](historical/)

All previous status updates, phase completion reports, and historical analysis documents are archived here for reference.

Key files:
- **AGENT_1_COMPLETION_REPORT.md** - Initial agent work
- **AGENT_2_IMPLEMENTATION_SUMMARY.md** - Agent 2 overview
- **AGENT_3_DELIVERABLES_CHECKLIST.md** - Agent 3 checklist
- **And 45+ more historical documents**

---

## RAG (Retrieval Augmented Generation) Documentation

**Location**: [rag/](rag/)

Documentation for the RAG knowledge base integration:
- RAG setup guides
- Implementation procedures
- Population strategies
- Quick reference

---

## Project Information

### Project Metadata
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - High-level project overview
- **[../README.md](../README.md)** - Main README

### Integration Guides
- **[S1_INTEGRATION_GUIDE.md](S1_INTEGRATION_GUIDE.md)** - S1 integration
- **[Hybrid_Architecture_Plan.md](Hybrid_Architecture_Plan.md)** - Hybrid architecture

---

## Configuration Files

### Root Level Configuration
```
README.md                    # Main project documentation
SETUP.md                     # Basic setup guide
.env.example                 # Environment variables template
config.yaml.example          # Configuration template
requirements.txt             # Python dependencies
docker-compose.yml          # Docker Compose configuration
Dockerfile                  # Application Docker image
```

### Terraform Configuration
```
deployment/aws/terraform/   # All Terraform Infrastructure as Code
├── main.tf                 # Main configuration
├── variables.tf            # Variable definitions
├── outputs.tf              # Output definitions
├── terraform.tfvars        # Environment-specific values
├── security-and-encryption.tf  # Security resources
├── secrets-management.tf    # Secrets management
└── modules/                # Reusable modules
```

### Kubernetes Configuration
Lean harness mode does not include bundled Kubernetes manifests.
Treat cluster deployment assets as optional, future add-ons.

---

## How to Use This Documentation

### For New Users
1. Start with [START_HERE.md](START_HERE.md)
2. Review [WHAT_YOU_ACTUALLY_NEED.md](WHAT_YOU_ACTUALLY_NEED.md)
3. Check [SECURITY-COMPLIANCE-SUMMARY.md](../SECURITY-COMPLIANCE-SUMMARY.md) for current status

### For Deployment
1. Review deployment guide in [deployment/](deployment/)
2. Follow [REMEDIATION-AGENT-X-PROMPT.md] for your phase
3. Use [QUICK_START_FINAL_SETUP.md](QUICK_START_FINAL_SETUP.md) for 5-minute setup

### For Security Review
1. Read [FEDRAMP-COMPLIANCE-AUDIT.md](FEDRAMP-COMPLIANCE-AUDIT.md)
2. Review [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md)
3. Check [STIG_COMPLIANCE_MATRIX.md](STIG_COMPLIANCE_MATRIX.md)

### For Operations
1. Review [OPERATIONAL_RUNBOOKS.md](OPERATIONAL_RUNBOOKS.md)
2. Check [SECURITY_RUNBOOKS.md](SECURITY_RUNBOOKS.md)
3. Monitor using [MONITORING_TESTING_ARCHITECTURE.md](MONITORING_TESTING_ARCHITECTURE.md)

---

## Documentation Statistics

- **Total Documentation Files**: 150+
- **Total Lines of Documentation**: 50,000+
- **Compliance Coverage**: 100% FedRAMP High
- **Architecture Decisions**: 4 ADRs
- **Security Controls**: 110+ FedRAMP controls
- **Terraform Code**: 5,000+ lines
- **Kubernetes Manifests**: 1,000+ lines

---

## Key Compliance Achievements

✅ **100% FedRAMP High Compliance**
- All 12 critical security gaps closed
- All audit logging implemented
- All encryption deployed
- All access controls hardened
- All network security configured

✅ **NIST 800-53 High Baseline**
- 110+ security controls implemented

✅ **STIG Compliance**
- All required hardening applied

✅ **FIPS 140-2**
- Cryptographic modules properly configured

---

## Support & Questions

### Documentation Issues
If you find documentation that is unclear or outdated, please:
1. Check the [historical/](historical/) folder for context
2. Review related architecture documents
3. Consult the [START_HERE.md](START_HERE.md) overview

### Security Questions
Refer to [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md) and security folder documents.

### Deployment Questions
Check the deployment folder and relevant remediation agent prompt.

### Compliance Questions
Review [FEDRAMP-COMPLIANCE-AUDIT.md](FEDRAMP-COMPLIANCE-AUDIT.md) and compliance matrices.

---

**Project Status**: Production Ready ✓
**Compliance**: 100% FedRAMP High ✓
**Security**: Enterprise Grade ✓
**Documentation**: Comprehensive ✓

---

Generated: 2025-11-09
