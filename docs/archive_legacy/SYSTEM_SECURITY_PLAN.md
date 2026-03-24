# System Security Plan (SSP)
## Purple Pipeline Parser Eater v9.0.0

**Document Classification**: Internal Use Only
**Last Updated**: 2025-10-10
**Version**: 1.0
**Next Review Date**: 2025-11-10

---

## 1. Executive Summary

### 1.1 System Overview

**System Name**: Purple Pipeline Parser Eater
**System Abbreviation**: PPPE
**Version**: 9.0.0
**System Type**: Automated Security Pipeline Processing Platform
**Deployment Environment**: AWS EKS (Kubernetes), Docker Compose
**Security Categorization**: MODERATE (FIPS 199)

**Purpose**: Purple Pipeline Parser Eater automates the extraction, processing, and transformation of security parsers from natural language descriptions into operational Observo.ai Lua pipelines. The system integrates with Anthropic Claude API for AI-powered code generation and SentinelOne for threat intelligence context.

### 1.2 System Sensitivity

| Category | Level | Justification |
|----------|-------|---------------|
| **Confidentiality** | MODERATE | Contains API keys, internal pipeline logic |
| **Integrity** | HIGH | Pipeline corruption could affect security monitoring |
| **Availability** | MODERATE | Temporary outages acceptable, not life-critical |

**Overall Categorization**: MODERATE per FIPS 199

### 1.3 Authorization Status

- **Authorization Date**: Pending
- **Authorizing Official**: [To Be Determined]
- **Authorization Termination Date**: [3 years from authorization]
- **Current Status**: In Authorization Process

---

## 2. System Description

### 2.1 System Function

Purple Pipeline Parser Eater provides:

1. **Natural Language Pipeline Generation**: Converts user descriptions into Lua pipelines
2. **Parser Repository Management**: Maintains library of security parsers
3. **Real-time Feedback Loop**: Interactive refinement of generated parsers
4. **Observo.ai Integration**: Direct deployment to Observo platform
5. **RAG-Enhanced Context**: GitHub documentation integration for improved accuracy
6. **Continuous Processing**: Automated conversion service for queued requests

### 2.2 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Web UI     │  │  REST API    │  │   CLI Tool   │         │
│  │  (Port 8080) │  │ (Port 8000)  │  │   (Direct)   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Application Layer                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Orchestrator (orchestrator.py)               │  │
│  │    - Request routing   - Environment expansion            │  │
│  │    - Configuration     - Parser validation                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────┬──────┴────────┬──────────────────────┐  │
│  │                   │               │                       │  │
│  ▼                   ▼               ▼                       ▼  │
│ ┌──────────────┐ ┌─────────────┐ ┌──────────────┐ ┌──────────┐│
│ │ Main Parser  │ │  Continuous │ │  RAG Auto    │ │  Web UI  ││
│ │  Generator   │ │  Conversion │ │   Updater    │ │ Feedback ││
│ │  (main.py)   │ │  Service    │ │ (GitHub)     │ │  (Flask) ││
│ └──────────────┘ └─────────────┘ └──────────────┘ └──────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Security Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Seccomp    │  │   AppArmor   │  │   Network    │         │
│  │   Profile    │  │   Profile    │  │   Policies   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ FIPS OpenSSL │  │ TLS 1.2/1.3  │  │ Read-only FS │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Anthropic   │  │ SentinelOne  │  │  Observo.ai  │         │
│  │ Claude API   │  │   Purple AI  │  │  Platform    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ AWS Secrets  │  │  CloudWatch  │  │   GitHub     │         │
│  │   Manager    │  │    Logs      │  │   API        │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 System Boundaries

**Internal Components** (within authorization boundary):
- Orchestrator service
- Main parser generator
- Continuous conversion service
- Web feedback UI
- RAG auto-updater
- Pipeline validator
- Parser output manager

**External Dependencies** (outside authorization boundary):
- Anthropic Claude API (api.anthropic.com)
- SentinelOne Platform (customer console URL)
- Observo.ai Platform (customer-specific)
- AWS Services (Secrets Manager, CloudWatch, KMS)
- GitHub API (github.com)

### 2.4 Network Architecture

**Production Deployment (AWS EKS)**:
```
Internet
    │
    ▼
┌─────────────────────────────────────────┐
│   AWS Application Load Balancer (ALB)   │
│   - TLS 1.2/1.3 termination             │
│   - WAF rules                           │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│   NGINX Ingress Controller              │
│   - cert-manager integration            │
│   - Rate limiting                       │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│   Kubernetes Service (ClusterIP)        │
│   - purple-parser:8080                  │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│   Purple Parser Pods (3 replicas)       │
│   - Network policies enforced           │
│   - Seccomp + AppArmor profiles         │
│   - Read-only root filesystem           │
└─────────────────────────────────────────┘
```

**Network Zones**:
- **DMZ**: ALB, NGINX Ingress (public-facing)
- **Application Zone**: Kubernetes pods (private subnet)
- **Data Zone**: AWS Secrets Manager, CloudWatch (VPC endpoints)

---

## 3. Security Controls

### 3.1 Control Framework

This SSP implements security controls from:
- **NIST SP 800-53 Rev 5**: Moderate baseline
- **DISA STIG**: Red Hat Enterprise Linux 9
- **FIPS 140-2**: Cryptographic module validation
- **CIS Kubernetes Benchmark**: v1.8.0

### 3.2 Control Summary

| Control Family | Total Controls | Implemented | Compliance |
|----------------|----------------|-------------|------------|
| Access Control (AC) | 10 | 7 | 70% |
| Audit & Accountability (AU) | 8 | 7 | 88% |
| Identification & Authentication (IA) | 6 | 4 | 67% |
| System & Communications Protection (SC) | 10 | 8 | 80% |
| System & Information Integrity (SI) | 12 | 9 | 75% |
| **TOTAL** | **46** | **35** | **76%** |

### 3.3 Access Control (AC)

#### AC-2: Account Management
**Implementation Status**: ✅ Implemented

- **How Met**:
  - No direct user accounts in application
  - Kubernetes RBAC for pod access (least privilege)
  - AWS IAM roles for service authentication
  - Service accounts with minimal permissions

- **Evidence**:
  - `deployment/k8s/rbac.yaml`: RBAC policies
  - `terraform/iam.tf`: IAM role definitions
  - Service account: `purple-parser` (namespace-scoped)

#### AC-3: Access Enforcement
**Implementation Status**: ✅ Implemented

- **How Met**:
  - Kubernetes network policies (deny-all default)
  - AppArmor mandatory access control
  - Seccomp system call filtering
  - Read-only root filesystem

- **Evidence**:
  - `security/apparmor-purple-parser`: AppArmor profile
  - `security/seccomp-purple-parser.json`: Seccomp profile
  - `deployment/k8s/network-policy-*.yaml`: Network policies

#### AC-4: Information Flow Enforcement
**Implementation Status**: ✅ Implemented

- **How Met**:
  - Network policies restrict pod-to-pod traffic
  - Egress limited to specific external services
  - TLS 1.2+ for all external communications
  - VPC endpoints for AWS services (no internet routing)

- **Evidence**:
  - `deployment/k8s/network-policy-purple-parser-egress.yaml`
  - Allowed destinations: AWS APIs, Anthropic API, S1 API
  - Blocked: all other egress traffic

#### AC-6: Least Privilege
**Implementation Status**: ✅ Implemented

- **How Met**:
  - Container runs as non-root user (UID 1001)
  - Capabilities dropped: ALL
  - Capabilities added: NET_BIND_SERVICE, CHOWN, SETUID, SETGID (minimal)
  - Seccomp blocks 400+ dangerous syscalls

- **Evidence**:
  - `Dockerfile.fips`: `USER 1001`
  - `deployment/k8s/deployment.yaml`: securityContext with dropped capabilities
  - `security/seccomp-purple-parser.json`: allowed syscalls whitelist

#### AC-17: Remote Access
**Implementation Status**: ✅ Implemented

- **How Met**:
  - All remote access via HTTPS only
  - TLS 1.2/1.3 with strong ciphersuites
  - Certificate-based authentication (X.509)
  - No SSH/RDP access to containers

- **Evidence**:
  - `deployment/k8s/ingress.yaml`: TLS configuration
  - `deployment/k8s/certificate.yaml`: cert-manager automation
  - NGINX annotations: `ssl-protocols: TLSv1.2 TLSv1.3`

### 3.4 Audit & Accountability (AU)

#### AU-2: Audit Events
**Implementation Status**: ✅ Implemented

- **How Met**:
  - Structured JSON logging (structlog)
  - Security events logged separately
  - All authentication/authorization events captured
  - API calls logged with request IDs

- **Evidence**:
  - `utils/security_logging.py`: SecurityEventLogger class
  - Log levels: INFO, WARNING, ERROR, CRITICAL
  - Security event types: authentication, authorization, input_validation

#### AU-3: Content of Audit Records
**Implementation Status**: ✅ Implemented

- **How Met**:
  - Timestamp (ISO 8601 UTC)
  - Event type and severity
  - User/service identity
  - Outcome (success/failure)
  - Request ID for correlation

- **Evidence**:
  - CloudWatch Formatter includes: timestamp, level, logger, source, request_id
  - Example: `{"timestamp": "2025-10-10T12:00:00Z", "level": "ERROR", "event_type": "authentication_failure", "user": "api_key_xyz", "outcome": "denied"}`

#### AU-6: Audit Review, Analysis, and Reporting
**Implementation Status**: ✅ Implemented

- **How Met**:
  - CloudWatch Logs Insights for analysis
  - Metric filters for critical events
  - CloudWatch Alarms for authentication failures
  - Weekly automated reports

- **Evidence**:
  - `terraform/cloudwatch-logs.tf`: Metric filters and alarms
  - Alarm: authentication failures > 5 in 5 minutes
  - SNS notifications to security team

#### AU-9: Protection of Audit Information
**Implementation Status**: ✅ Implemented

- **How Met**:
  - CloudWatch Logs encrypted at rest (KMS)
  - TLS 1.2 for log transmission
  - IAM policies restrict log access
  - 90-day retention with immutability

- **Evidence**:
  - `terraform/cloudwatch-logs.tf`: `kms_key_id = aws_kms_key.logs.arn`
  - IAM policy: fluentd write-only, security team read-only
  - No log deletion permissions for application service accounts

#### AU-11: Audit Record Retention
**Implementation Status**: ✅ Implemented

- **How Met**:
  - 90-day retention in CloudWatch Logs
  - Automated archival to S3 Glacier (long-term)
  - Retention policy enforced by CloudWatch

- **Evidence**:
  - `terraform/cloudwatch-logs.tf`: `retention_in_days = 90`

### 3.5 Identification & Authentication (IA)

#### IA-2: Identification and Authentication (Organizational Users)
**Implementation Status**: ⚠️ Partial

- **How Met**:
  - API key authentication for external services
  - AWS IAM roles for service-to-service
  - No interactive user authentication (system-to-system only)

- **Gap**: No multi-factor authentication (not applicable for API-only system)

#### IA-5: Authenticator Management
**Implementation Status**: ✅ Implemented

- **How Met**:
  - API keys stored in AWS Secrets Manager
  - KMS encryption for secrets at rest
  - Automatic secret rotation (90 days)
  - No hardcoded credentials

- **Evidence**:
  - `utils/aws_secrets_manager.py`: Secrets retrieval
  - `terraform/secrets.tf`: Secret rotation configuration
  - Zero hardcoded secrets in codebase (verified by scan)

#### IA-7: Cryptographic Module Authentication
**Implementation Status**: ✅ Implemented

- **How Met**:
  - FIPS 140-2 validated OpenSSL module
  - Runtime FIPS mode verification
  - Certificate-based authentication for TLS

- **Evidence**:
  - `scripts/verify-fips.sh`: FIPS validation
  - OpenSSL 3.0.7-27.el9 (FIPS 140-2 Certificate #4282)

### 3.6 System & Communications Protection (SC)

#### SC-7: Boundary Protection
**Implementation Status**: ✅ Implemented

- **How Met**:
  - Kubernetes network policies (deny-all default)
  - ALB with WAF rules
  - Security groups (AWS VPC)
  - Ingress/egress filtering

- **Evidence**:
  - `deployment/k8s/network-policy-deny-all-default.yaml`
  - `terraform/eks-network-policies.tf`: Security group rules
  - Only ports 80/443 exposed externally

#### SC-8: Transmission Confidentiality and Integrity
**Implementation Status**: ✅ Implemented

- **How Met**:
  - TLS 1.2/1.3 for all external communications
  - Strong ciphersuites (ECDHE, AES-GCM)
  - Certificate pinning for internal services
  - HSTS headers

- **Evidence**:
  - `deployment/k8s/ingress.yaml`: `ssl-protocols: TLSv1.2 TLSv1.3`
  - Ciphersuites: ECDHE-ECDSA-AES128-GCM-SHA256, ECDHE-RSA-AES256-GCM-SHA384
  - `components/web_feedback_ui.py`: HSTS headers added

#### SC-12: Cryptographic Key Establishment and Management
**Implementation Status**: ✅ Implemented

- **How Met**:
  - AWS KMS for key management
  - Automated key rotation (annual)
  - cert-manager for TLS certificate lifecycle
  - Secrets Manager for API key rotation

- **Evidence**:
  - `terraform/secrets.tf`: KMS key with rotation enabled
  - `deployment/k8s/certificate.yaml`: 90-day cert duration, 30-day renewal
  - Key rotation: automatic via AWS KMS

#### SC-13: Cryptographic Protection
**Implementation Status**: ✅ Implemented

- **How Met**:
  - FIPS 140-2 validated cryptography
  - SHA-256/SHA3-256 for hashing
  - AES-256-GCM for encryption
  - RSA-4096 for certificates

- **Evidence**:
  - `Dockerfile.fips`: FIPS mode enabled
  - `scripts/replace_md5_with_sha256.py`: MD5 eliminated
  - All cryptography via FIPS-validated OpenSSL

#### SC-28: Protection of Information at Rest
**Implementation Status**: ✅ Implemented

- **How Met**:
  - AWS EBS encryption (AES-256)
  - Secrets Manager encryption (KMS)
  - CloudWatch Logs encryption (KMS)
  - Persistent volumes encrypted

- **Evidence**:
  - `terraform/eks.tf`: EBS encryption enabled
  - `terraform/secrets.tf`: KMS encryption for secrets
  - `terraform/cloudwatch-logs.tf`: KMS encryption for logs

### 3.7 System & Information Integrity (SI)

#### SI-2: Flaw Remediation
**Implementation Status**: ✅ Implemented

- **How Met**:
  - Automated vulnerability scanning (Trivy, pip-audit)
  - Daily scans in CI/CD pipeline
  - Critical vulnerabilities blocked from deployment
  - 30-day remediation SLA for high/critical

- **Evidence**:
  - `.github/workflows/vulnerability-scan.yml`: Daily scans
  - `scripts/scan-vulnerabilities.sh`: Trivy integration
  - GitHub Security tab: SARIF report upload

#### SI-3: Malicious Code Protection
**Implementation Status**: ✅ Implemented

- **How Met**:
  - Container image scanning (Trivy)
  - Dependency integrity verification (hash pinning)
  - File integrity monitoring (AIDE)
  - Seccomp prevents malicious syscalls

- **Evidence**:
  - `requirements.lock`: SHA-256 hashes for all dependencies
  - `security/aide.conf`: File integrity monitoring
  - Trivy scans: daily image vulnerability checks

#### SI-4: System Monitoring
**Implementation Status**: ✅ Implemented

- **How Met**:
  - CloudWatch Logs centralized logging
  - Fluentd log aggregation
  - CloudWatch Alarms for security events
  - Prometheus metrics (optional)

- **Evidence**:
  - `deployment/k8s/fluentd-config.yaml`: Log collection
  - `terraform/cloudwatch-logs.tf`: Metric filters and alarms
  - Monitored events: authentication failures, critical errors

#### SI-7: Software, Firmware, and Information Integrity
**Implementation Status**: ✅ Implemented

- **How Met**:
  - AIDE file integrity monitoring
  - Docker image digest pinning
  - Dependency hash verification
  - Read-only root filesystem

- **Evidence**:
  - `security/aide.conf`: Critical files monitored
  - `docker-compose.yml`: Image digests (sha256:...)
  - `requirements.lock`: --hash flags
  - `deployment/k8s/deployment.yaml`: readOnlyRootFilesystem: true

#### SI-10: Information Input Validation
**Implementation Status**: ✅ Implemented

- **How Met**:
  - Pipeline validator class
  - Input sanitization for all user inputs
  - Path traversal prevention
  - XSS/CSRF protection in web UI

- **Evidence**:
  - `components/pipeline_validator.py`: Comprehensive validation
  - `components/parser_output_manager.py`: Path sanitization
  - `components/web_feedback_ui.py`: XSS escaping, CSRF tokens

---

## 4. Data Protection

### 4.1 Data Classification

| Data Type | Classification | Storage Location | Encryption |
|-----------|----------------|------------------|------------|
| **API Keys** | CONFIDENTIAL | AWS Secrets Manager | AES-256 (KMS) |
| **Generated Pipelines** | INTERNAL | EBS volumes, S3 | AES-256 (EBS) |
| **Application Logs** | INTERNAL | CloudWatch Logs | AES-256 (KMS) |
| **User Inputs** | INTERNAL | Temporary (memory) | In-transit TLS |
| **Source Code** | INTERNAL | GitHub (private) | GitHub encryption |

### 4.2 Data Flow

**Input → Processing → Output**:

1. **User Input** (HTTPS/TLS 1.2+)
   - Description of desired parser
   - Arrives via Web UI or API
   - Input validation applied immediately

2. **Internal Processing** (Memory)
   - Orchestrator routes request
   - Claude API generates Lua code
   - Pipeline validator checks syntax
   - Stored in memory only (ephemeral)

3. **Output Generation** (Encrypted Storage)
   - Validated pipeline written to `/app/output/`
   - Encrypted EBS volume (AES-256)
   - Optional push to Observo.ai

4. **Logging** (CloudWatch)
   - Security events logged
   - Transmitted via TLS 1.2
   - Stored encrypted (KMS)

### 4.3 Data Retention

| Data Type | Retention Period | Disposal Method |
|-----------|------------------|-----------------|
| **Application Logs** | 90 days | Automatic CloudWatch expiration |
| **Generated Pipelines** | 30 days | Automated cleanup script |
| **Secrets** | Until rotated | AWS Secrets Manager soft delete (30d) |
| **Container Images** | 60 days | ECR lifecycle policy |

---

## 5. Security Operations

### 5.1 Vulnerability Management

**Process**:
1. **Daily Scanning**: Trivy + pip-audit (automated)
2. **Severity Assessment**: CVSS scoring
3. **Prioritization**: Critical > High > Medium > Low
4. **Remediation**:
   - Critical: 7 days
   - High: 30 days
   - Medium: 90 days
   - Low: 180 days or next release
5. **Verification**: Re-scan after patch applied

**Tools**:
- Trivy: Container image scanning
- pip-audit: Python dependency scanning
- GitHub Dependabot: Automated PRs for updates

### 5.2 Incident Response

**Response Team**:
- Security Lead: [Name]
- DevOps Lead: [Name]
- Development Lead: [Name]
- On-call Engineer: [24/7 rotation]

**Incident Types**:
- **P0 - Critical**: Data breach, system compromise
- **P1 - High**: Authentication bypass, privilege escalation
- **P2 - Medium**: Vulnerability exploit, DoS
- **P3 - Low**: Policy violation, configuration error

**Response SLAs**:
- P0: 15-minute initial response, 1-hour containment
- P1: 1-hour initial response, 4-hour containment
- P2: 4-hour initial response, 24-hour containment
- P3: 24-hour initial response, 7-day resolution

### 5.3 Change Management

**Change Categories**:
- **Emergency**: Security patch (expedited approval)
- **Standard**: Feature release (full review process)
- **Normal**: Configuration change (peer review)

**Approval Requirements**:
- Emergency: Security Lead + 1 peer
- Standard: Security Lead + Development Lead + QA
- Normal: 2 peer reviews

### 5.4 Backup & Recovery

**Backup Strategy**:
- **Configuration**: Git version control (GitHub)
- **Secrets**: AWS Secrets Manager (automatic backup)
- **Logs**: CloudWatch (90-day retention)
- **Persistent Data**: EBS snapshots (daily, 30-day retention)

**Recovery Objectives**:
- RTO (Recovery Time Objective): 4 hours
- RPO (Recovery Point Objective): 24 hours

---

## 6. Compliance & Attestation

### 6.1 FIPS 140-2 Compliance

**Status**: ✅ Compliant

**Evidence**:
- Base image: RHEL UBI 9 (FIPS mode)
- OpenSSL: 3.0.7-27.el9 (Certificate #4282)
- Runtime verification: `scripts/verify-fips.sh`
- All cryptography via FIPS-validated modules

**Validation**:
- Automated daily checks in CI/CD
- Kubernetes liveness probe verifies FIPS mode
- Container startup fails if FIPS verification fails

### 6.2 STIG Compliance

**Status**: ⚠️ 76% Compliant (35/46 controls)

**Major Gaps**:
1. Multi-factor authentication (IA-2): Not applicable (API-only system)
2. User training (AT-2): Documentation in progress
3. Penetration testing (CA-8): Scheduled for Q4 2025

**Remediation Plan**:
- Complete Phase 4 documentation (Week 1)
- Schedule external penetration test (Week 4)
- User training materials (Week 2)

### 6.3 Continuous Monitoring

**Automated Monitoring**:
- ✅ Vulnerability scanning: Daily
- ✅ File integrity: Every 6 hours
- ✅ FIPS compliance: Continuous (liveness probe)
- ✅ Certificate expiration: Continuous (cert-manager)
- ✅ Log analysis: Real-time (CloudWatch)

**Manual Reviews**:
- Security event logs: Weekly
- Access control policies: Monthly
- Incident response procedures: Quarterly
- Full security assessment: Annually

---

## 7. Roles & Responsibilities

### 7.1 Security Roles

| Role | Responsibilities | Personnel |
|------|------------------|-----------|
| **Information System Security Officer (ISSO)** | Overall security posture, compliance, risk management | [Name] |
| **System Owner** | Business decisions, authorization, budget | [Name] |
| **System Administrator** | Day-to-day operations, patching, monitoring | [Name] |
| **Security Engineer** | Security controls implementation, incident response | [Name] |
| **Developer** | Secure coding, vulnerability remediation | [Team] |

### 7.2 Access Roles

| Role | Access Level | Granted To |
|------|--------------|------------|
| **Admin** | Full cluster access (kubectl, AWS console) | DevOps team (2 persons) |
| **Developer** | Read-only cluster access, code repository | Development team (5 persons) |
| **Viewer** | Logs, metrics (CloudWatch, Grafana) | Operations team (3 persons) |
| **Auditor** | Read-only logs, compliance reports | Security team (2 persons) |

---

## 8. Dependencies & Interconnections

### 8.1 External Service Dependencies

| Service | Purpose | Data Exchanged | Security Controls |
|---------|---------|----------------|-------------------|
| **Anthropic Claude API** | AI code generation | User prompts, generated code | TLS 1.2, API key (Secrets Manager) |
| **SentinelOne** | Threat intelligence | Query context, parser metadata | TLS 1.2, API key (Secrets Manager) |
| **Observo.ai** | Pipeline deployment | Lua pipelines, metadata | TLS 1.2, API key (Secrets Manager) |
| **AWS Secrets Manager** | Secret storage | API keys, credentials | KMS encryption, IAM policies |
| **AWS CloudWatch** | Logging, monitoring | Application logs, metrics | TLS 1.2, KMS encryption |
| **GitHub** | RAG documentation | Public docs, issue tracking | TLS 1.2, API key (rate limit only) |

### 8.2 Interconnection Security Agreements (ISAs)

**Required ISAs**:
- ✅ AWS Services: Covered by AWS Shared Responsibility Model
- ⚠️ Anthropic: Commercial terms accepted (no formal ISA)
- ⚠️ SentinelOne: Customer agreement (review for ISA requirements)
- ⚠️ Observo.ai: Customer agreement (review for ISA requirements)

**Action Items**:
- Review Anthropic terms for data handling (Week 1)
- Request ISA from SentinelOne (Week 2)
- Request ISA from Observo.ai (Week 2)

---

## 9. Security Testing

### 9.1 Automated Testing

| Test Type | Frequency | Tool | Pass Criteria |
|-----------|-----------|------|---------------|
| **Vulnerability Scan** | Daily | Trivy, pip-audit | 0 critical, <5 high |
| **FIPS Verification** | Every deployment | verify-fips.sh | 100% pass |
| **File Integrity** | Every 6 hours | AIDE | 0 unauthorized changes |
| **Network Policy** | Every deployment | k8s admission controller | All policies enforced |
| **Secret Rotation** | 90 days | AWS Secrets Manager | Automatic |

### 9.2 Manual Testing

| Test Type | Frequency | Performed By | Last Completed |
|-----------|-----------|--------------|----------------|
| **Penetration Test** | Annually | External firm | Planned Q4 2025 |
| **Security Review** | Quarterly | Security team | 2025-10-01 |
| **Incident Response Drill** | Semi-annually | All teams | Planned Q1 2026 |
| **Compliance Audit** | Annually | External auditor | Planned Q4 2025 |

---

## 10. Known Risks & Mitigations

### 10.1 Current Risks

| Risk ID | Description | Likelihood | Impact | Mitigation |
|---------|-------------|------------|--------|------------|
| **R-001** | Anthropic API compromise | LOW | HIGH | API key rotation (90d), rate limiting, input validation |
| **R-002** | Generated Lua code injection | LOW | CRITICAL | Pipeline validator, sandbox execution (future), output escaping |
| **R-003** | Supply chain attack | MEDIUM | HIGH | Dependency hash pinning, daily scanning, SBOM generation |
| **R-004** | Container escape | LOW | HIGH | Seccomp + AppArmor + network policies + read-only FS |
| **R-005** | Secrets exposure in logs | LOW | HIGH | Secret redaction in logs, CloudWatch encryption |

### 10.2 Accepted Risks

| Risk ID | Description | Justification |
|---------|-------------|---------------|
| **AR-001** | No MFA for API access | API-only system, compensating control: API key rotation + rate limiting |
| **AR-002** | Lua code execution not sandboxed | Low likelihood of malicious input, validator provides basic protection |
| **AR-003** | Reliance on external AI service | Business requirement, no alternative, API key protection implemented |

---

## 11. Contingency Planning

### 11.1 Disaster Recovery

**Scenario: Complete AWS Region Failure**
- **RTO**: 8 hours
- **RPO**: 24 hours
- **Recovery Steps**:
  1. Activate DR region (us-west-2)
  2. Restore Terraform state from S3 backend
  3. Re-deploy infrastructure via Terraform
  4. Restore secrets from AWS Secrets Manager replica
  5. Restore application from Docker registry
  6. Update DNS to point to DR region

**Scenario: Container Image Registry Unavailable**
- **RTO**: 2 hours
- **RPO**: 0 (no data loss)
- **Recovery Steps**:
  1. Pull images from backup registry (Docker Hub)
  2. Re-tag and push to temporary ECR
  3. Update deployment manifests
  4. Rolling restart of pods

**Scenario: Anthropic API Outage**
- **RTO**: N/A (external dependency)
- **RPO**: N/A
- **Recovery Steps**:
  1. Queue incoming requests
  2. Return HTTP 503 with retry-after header
  3. Monitor Anthropic status page
  4. Process queue when service restored

### 11.2 Incident Response

See separate document: `docs/SECURITY_INCIDENT_RESPONSE_PLAN.md`

---

## 12. System Lifecycle

### 12.1 Development Phase

**Security Activities**:
- Threat modeling
- Secure coding training
- Static code analysis (SAST)
- Dependency vulnerability scanning
- Security unit tests

**Deliverables**:
- Threat model document
- Security test results
- Code review sign-offs

### 12.2 Deployment Phase

**Security Activities**:
- Container image scanning
- Infrastructure as Code (IaC) security review
- Secrets provisioning (AWS Secrets Manager)
- Network policy deployment
- FIPS compliance verification

**Deliverables**:
- Deployment checklist (completed)
- FIPS verification report
- Vulnerability scan report (pre-deploy)

### 12.3 Operations Phase

**Security Activities**:
- Daily vulnerability scanning
- File integrity monitoring
- Security event monitoring
- Incident response
- Patch management

**Deliverables**:
- Weekly security reports
- Monthly compliance reports
- Incident reports (as needed)

### 12.4 Decommissioning Phase

**Security Activities**:
- Data sanitization
- Secret revocation
- Infrastructure teardown
- Final audit log export
- Certificate revocation

**Deliverables**:
- Decommissioning checklist
- Data destruction certificate
- Final security report

---

## 13. Points of Contact

### 13.1 Technical Contacts

| Role | Name | Email | Phone |
|------|------|-------|-------|
| **System Owner** | [Name] | system-owner@company.com | +1-XXX-XXX-XXXX |
| **ISSO** | [Name] | isso@company.com | +1-XXX-XXX-XXXX |
| **System Administrator** | [Name] | sysadmin@company.com | +1-XXX-XXX-XXXX |
| **Security Engineer** | [Name] | security@company.com | +1-XXX-XXX-XXXX |

### 13.2 Management Contacts

| Role | Name | Email | Phone |
|------|------|-------|-------|
| **Authorizing Official** | [Name] | ao@company.com | +1-XXX-XXX-XXXX |
| **CISO** | [Name] | ciso@company.com | +1-XXX-XXX-XXXX |
| **Engineering Director** | [Name] | eng-director@company.com | +1-XXX-XXX-XXXX |

### 13.3 Escalation Path

**Security Incidents**:
1. On-call Engineer (immediate)
2. Security Engineer (15 minutes)
3. ISSO (1 hour)
4. CISO (P0 incidents only)

**Business Impact**:
1. System Owner (immediate)
2. Engineering Director (30 minutes)
3. CTO (P0 incidents only)

---

## 14. Appendices

### Appendix A: Acronyms

| Acronym | Definition |
|---------|------------|
| **AIDE** | Advanced Intrusion Detection Environment |
| **ALB** | Application Load Balancer |
| **ATO** | Authorization to Operate |
| **CISO** | Chief Information Security Officer |
| **FIPS** | Federal Information Processing Standard |
| **IAM** | Identity and Access Management |
| **ISA** | Interconnection Security Agreement |
| **ISSO** | Information System Security Officer |
| **KMS** | Key Management Service |
| **NIST** | National Institute of Standards and Technology |
| **PPPE** | Purple Pipeline Parser Eater |
| **RAG** | Retrieval-Augmented Generation |
| **RBAC** | Role-Based Access Control |
| **RPO** | Recovery Point Objective |
| **RTO** | Recovery Time Objective |
| **SAST** | Static Application Security Testing |
| **STIG** | Security Technical Implementation Guide |
| **TLS** | Transport Layer Security |
| **VPC** | Virtual Private Cloud |

### Appendix B: References

1. NIST SP 800-53 Rev 5: Security and Privacy Controls for Information Systems
2. NIST SP 800-37 Rev 2: Risk Management Framework
3. FIPS 140-2: Security Requirements for Cryptographic Modules
4. DISA STIG: Red Hat Enterprise Linux 9 Security Technical Implementation Guide
5. CIS Kubernetes Benchmark v1.8.0
6. OWASP Top 10 (2021)

### Appendix C: Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-10 | Security Team | Initial SSP creation |

---

**Document Approval**

| Role | Name | Signature | Date |
|------|------|-----------|------|
| **System Owner** | [Name] | _____________ | _______ |
| **ISSO** | [Name] | _____________ | _______ |
| **Authorizing Official** | [Name] | _____________ | _______ |

---

**End of System Security Plan**
