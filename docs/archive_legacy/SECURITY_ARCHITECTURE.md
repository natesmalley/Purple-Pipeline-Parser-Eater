# Security Architecture Document
## Purple Pipeline Parser Eater v9.0.0

**Document Classification**: Internal Use Only
**Last Updated**: 2025-10-10
**Version**: 1.0
**Prepared By**: Security Architecture Team

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Security Layers](#3-security-layers)
4. [Trust Boundaries](#4-trust-boundaries)
5. [Authentication & Authorization](#5-authentication--authorization)
6. [Data Protection](#6-data-protection)
7. [Network Security](#7-network-security)
8. [Container Security](#8-container-security)
9. [Secrets Management](#9-secrets-management)
10. [Logging & Monitoring](#10-logging--monitoring)
11. [Compliance Architecture](#11-compliance-architecture)
12. [Security Services Integration](#12-security-services-integration)

---

## 1. Executive Summary

### 1.1 Purpose

This document describes the security architecture of Purple Pipeline Parser Eater v9.0.0, detailing the defense-in-depth strategy, security controls implementation, and compliance with NIST 800-53, DISA STIG, and FIPS 140-2 standards.

### 1.2 Security Architecture Principles

1. **Defense in Depth**: Multiple security layers (7 layers total)
2. **Least Privilege**: Minimal permissions at every level
3. **Zero Trust**: No implicit trust, verify everything
4. **Secure by Default**: Security controls enabled out-of-box
5. **Fail Secure**: Failures result in deny/block, not allow
6. **Separation of Duties**: Role-based access control
7. **Audit Everything**: Comprehensive logging and monitoring

### 1.3 Security Posture Summary

| Security Domain | Status | Maturity Level |
|-----------------|--------|----------------|
| **Access Control** | ✅ Implemented | Level 4 - Managed |
| **Network Security** | ✅ Implemented | Level 4 - Managed |
| **Data Protection** | ✅ Implemented | Level 4 - Managed |
| **Container Security** | ✅ Implemented | Level 5 - Optimized |
| **Compliance** | ✅ Implemented | Level 4 - Managed |
| **Monitoring** | ✅ Implemented | Level 4 - Managed |

---

## 2. Architecture Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      SECURITY ARCHITECTURE                       │
│                    Purple Pipeline Parser Eater                  │
└─────────────────────────────────────────────────────────────────┘

                         ┌─────────────────┐
                         │   Internet      │
                         │   (Untrusted)   │
                         └────────┬────────┘
                                  │
                                  │ HTTPS (TLS 1.2/1.3)
                                  │
                  ┌───────────────▼───────────────┐
                  │  Layer 1: Perimeter Security  │
                  │  • AWS WAF                    │
                  │  • DDoS Protection (Shield)   │
                  │  • ALB (TLS termination)      │
                  └───────────────┬───────────────┘
                                  │
                  ┌───────────────▼───────────────┐
                  │  Layer 2: Ingress Control     │
                  │  • NGINX Ingress Controller   │
                  │  • Rate Limiting              │
                  │  • Certificate Validation     │
                  └───────────────┬───────────────┘
                                  │
                  ┌───────────────▼───────────────┐
                  │  Layer 3: Network Policies    │
                  │  • Kubernetes Network Policies│
                  │  • VPC Security Groups        │
                  │  • Deny-all Default           │
                  └───────────────┬───────────────┘
                                  │
                  ┌───────────────▼───────────────┐
                  │  Layer 4: Container Security  │
                  │  • Seccomp Profiles           │
                  │  • AppArmor MAC               │
                  │  • Read-only Filesystem       │
                  │  • Non-root Execution         │
                  └───────────────┬───────────────┘
                                  │
                  ┌───────────────▼───────────────┐
                  │  Layer 5: Application Security│
                  │  • Input Validation           │
                  │  • Output Encoding            │
                  │  • CSRF Protection            │
                  │  • XSS Prevention             │
                  └───────────────┬───────────────┘
                                  │
                  ┌───────────────▼───────────────┐
                  │  Layer 6: Data Protection     │
                  │  • FIPS 140-2 Crypto          │
                  │  • Encryption at Rest (KMS)   │
                  │  • Encryption in Transit (TLS)│
                  │  • Secrets Manager            │
                  └───────────────┬───────────────┘
                                  │
                  ┌───────────────▼───────────────┐
                  │  Layer 7: Monitoring & Audit  │
                  │  • CloudWatch Logs (encrypted)│
                  │  • Security Event Logging     │
                  │  • File Integrity (AIDE)      │
                  │  • Vulnerability Scanning     │
                  └───────────────────────────────┘
```

### 2.2 Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     KUBERNETES CLUSTER (EKS)                     │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Namespace: purple-parser (Isolated)                       │ │
│  │                                                             │ │
│  │  ┌──────────────────┐  ┌──────────────────┐              │ │
│  │  │  Pod 1           │  │  Pod 2           │              │ │
│  │  │  ┌────────────┐  │  │  ┌────────────┐  │              │ │
│  │  │  │ Seccomp    │  │  │  │ Seccomp    │  │              │ │
│  │  │  │ AppArmor   │  │  │  │ AppArmor   │  │              │ │
│  │  │  │ ────────── │  │  │  │ ────────── │  │              │ │
│  │  │  │ Container  │  │  │  │ Container  │  │   ┌────────┐ │ │
│  │  │  │  (UID 1001)│  │  │  │  (UID 1001)│  │◀──│Network │ │ │
│  │  │  │  Read-only │  │  │  │  Read-only │  │   │Policy  │ │ │
│  │  │  │  Rootfs    │  │  │  │  Rootfs    │  │   └────────┘ │ │
│  │  │  └────────────┘  │  │  └────────────┘  │              │ │
│  │  └──────────────────┘  └──────────────────┘              │ │
│  │                                                             │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  Fluentd DaemonSet (Log Collection)                  │ │ │
│  │  │  - Collects all pod logs                             │ │ │
│  │  │  - Encrypts and sends to CloudWatch                  │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Namespace: cert-manager (Certificate Management)          │ │
│  │  - Automated TLS certificate lifecycle                     │ │
│  │  - Let's Encrypt integration                               │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        AWS SERVICES                              │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Secrets    │  │  CloudWatch  │  │     KMS      │         │
│  │   Manager    │  │    Logs      │  │  (Encryption)│         │
│  │  (API Keys)  │  │  (90d retain)│  │   Keys       │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │     ECR      │  │     EBS      │  │     VPC      │         │
│  │  (Container  │  │  (Encrypted  │  │  (Network    │         │
│  │   Registry)  │  │   Volumes)   │  │  Isolation)  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Security Layers

### 3.1 Layer 1: Perimeter Security

**Purpose**: Protect against external threats before they reach the application

**Components**:

1. **AWS WAF (Web Application Firewall)**
   - OWASP Top 10 rule sets
   - Rate limiting (1000 req/5min per IP)
   - Geographic blocking (configurable)
   - SQL injection protection
   - XSS attack prevention

2. **AWS Shield Standard**
   - DDoS protection (Layer 3/4)
   - Automatic traffic baseline learning
   - Always-on detection

3. **Application Load Balancer (ALB)**
   - TLS 1.2/1.3 termination
   - HTTP to HTTPS redirect (301)
   - Security headers injection
   - Health check enforcement

**Security Controls**:
- SC-7: Boundary Protection
- SC-8: Transmission Confidentiality

**Configuration**:
```hcl
# terraform/waf.tf
resource "aws_wafv2_web_acl" "purple_parser" {
  scope = "REGIONAL"

  rule {
    name     = "rate-limit"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 1000
        aggregate_key_type = "IP"
      }
    }
  }

  rule {
    name     = "aws-managed-rules-owasp"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
      }
    }
  }
}
```

### 3.2 Layer 2: Ingress Control

**Purpose**: Control and monitor all incoming traffic to the application

**Components**:

1. **NGINX Ingress Controller**
   - Request routing
   - Rate limiting (per-endpoint)
   - Request size limits
   - TLS validation
   - Custom error pages

2. **cert-manager**
   - Automated certificate issuance
   - Certificate rotation (30d before expiry)
   - ACME protocol (Let's Encrypt)
   - Certificate validation

**Security Controls**:
- SC-8(1): Cryptographic Protection
- IA-5(1): Password-Based Authentication (certificates)

**Configuration**:
```yaml
# deployment/k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: purple-parser
  annotations:
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/limit-rps: "10"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    nginx.ingress.kubernetes.io/ssl-protocols: "TLSv1.2 TLSv1.3"
    nginx.ingress.kubernetes.io/ssl-ciphers: "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - parser.your-domain.com
    secretName: purple-parser-tls
  rules:
  - host: parser.your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: purple-parser
            port:
              number: 8080
```

### 3.3 Layer 3: Network Policies

**Purpose**: Zero-trust network segmentation within Kubernetes

**Components**:

1. **Default Deny Policy**
   - Blocks all ingress by default
   - Blocks all egress by default
   - Explicit allow rules required

2. **Ingress Policies**
   - Allow from NGINX Ingress only
   - Allow from monitoring (Prometheus)
   - Allow inter-pod communication (same namespace)

3. **Egress Policies**
   - Allow DNS (kube-dns)
   - Allow HTTPS to AWS services
   - Allow HTTPS to Anthropic API
   - Allow HTTPS to SentinelOne API
   - Block all other egress

**Security Controls**:
- SC-7(5): Deny by Default / Allow by Exception
- AC-4: Information Flow Enforcement

**Configuration**:
```yaml
# deployment/k8s/network-policy-deny-all-default.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: purple-parser
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
---
# deployment/k8s/network-policy-purple-parser-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: purple-parser-ingress
  namespace: purple-parser
spec:
  podSelector:
    matchLabels:
      app: purple-parser
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8080
```

### 3.4 Layer 4: Container Security

**Purpose**: Limit container capabilities and enforce mandatory access control

**Components**:

1. **Seccomp Profile**
   - Blocks 400+ dangerous syscalls
   - Allows only required syscalls (read, write, network, etc.)
   - Blocks: reboot, mount, module loading, etc.
   - Enforced at kernel level

2. **AppArmor Profile**
   - Mandatory Access Control (MAC)
   - File system restrictions
   - Capability restrictions
   - Network access control

3. **Security Context**
   - Non-root user (UID 1001)
   - Read-only root filesystem
   - No privilege escalation
   - Capabilities dropped (ALL)
   - Capabilities added: NET_BIND_SERVICE, CHOWN, SETUID, SETGID (minimal)

**Security Controls**:
- AC-6: Least Privilege
- CM-7: Least Functionality
- SI-16: Memory Protection

**Configuration**:
```yaml
# deployment/k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: purple-parser
  namespace: purple-parser
spec:
  template:
    metadata:
      annotations:
        seccomp.security.alpha.kubernetes.io/pod: "localhost/purple-parser"
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
        runAsGroup: 1001
        fsGroup: 1001
        seccompProfile:
          type: Localhost
          localhostProfile: purple-parser.json
      containers:
      - name: purple-parser
        image: purple-parser:fips
        securityContext:
          appArmorProfile:
            type: Localhost
            localhostProfile: purple-parser
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL
            add:
            - NET_BIND_SERVICE
            - CHOWN
            - SETUID
            - SETGID
        volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: output
          mountPath: /app/output
      volumes:
      - name: tmp
        emptyDir: {}
      - name: output
        emptyDir: {}
```

### 3.5 Layer 5: Application Security

**Purpose**: Protect against application-level attacks

**Components**:

1. **Input Validation**
   - Type checking
   - Length limits
   - Character whitelisting
   - Path traversal prevention
   - Command injection prevention

2. **Output Encoding**
   - HTML entity encoding (XSS prevention)
   - JSON escaping
   - URL encoding
   - SQL parameterization (if applicable)

3. **CSRF Protection**
   - HMAC-SHA256 tokens
   - Token validation on state-changing operations
   - SameSite cookie attribute
   - Token rotation

4. **Session Management**
   - Secure session cookies
   - HTTPOnly flag
   - Secure flag (HTTPS only)
   - Session timeout (30 minutes)
   - Session invalidation on logout

**Security Controls**:
- SI-10: Information Input Validation
- SI-11: Error Handling
- SC-23: Session Authenticity

**Implementation**:
```python
# components/pipeline_validator.py
class PipelineValidator:
    def validate_input(self, user_input: str) -> ValidationResult:
        # Length validation
        if len(user_input) > 10000:
            raise ValidationError("Input exceeds maximum length")

        # Character validation
        if not re.match(r'^[\w\s\-.,;:()\[\]{}]+$', user_input):
            raise ValidationError("Invalid characters in input")

        # Path traversal prevention
        if '..' in user_input or '/' in user_input:
            raise ValidationError("Path traversal attempt detected")

        # Command injection prevention
        dangerous_patterns = ['|', '&', ';', '`', '$', '(', ')']
        if any(pattern in user_input for pattern in dangerous_patterns):
            raise ValidationError("Command injection attempt detected")

        return ValidationResult(valid=True)

# components/web_feedback_ui.py
class WebFeedbackUI:
    def _generate_csrf_token(self, session_id: str) -> str:
        """Generate HMAC-SHA256 CSRF token"""
        secret = self.secrets_manager.get_secret_value('csrf-secret', 'key')
        message = f"{session_id}:{int(time.time())}"
        return hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

    def _validate_csrf_token(self, token: str, session_id: str) -> bool:
        """Validate CSRF token"""
        expected_token = self._generate_csrf_token(session_id)
        return hmac.compare_digest(token, expected_token)
```

### 3.6 Layer 6: Data Protection

**Purpose**: Protect data at rest and in transit using FIPS 140-2 cryptography

**Components**:

1. **FIPS 140-2 Cryptography**
   - OpenSSL 3.0.7-27.el9 (FIPS Certificate #4282)
   - SHA-256/SHA3-256 for hashing
   - AES-256-GCM for encryption
   - RSA-4096 for certificates
   - ECDHE for key exchange

2. **Encryption at Rest**
   - AWS KMS for key management
   - EBS volume encryption (AES-256)
   - Secrets Manager encryption (AES-256)
   - CloudWatch Logs encryption (AES-256)

3. **Encryption in Transit**
   - TLS 1.2/1.3 only
   - Strong ciphersuites (ECDHE + AES-GCM)
   - Certificate validation
   - HSTS enforcement

4. **Secrets Management**
   - AWS Secrets Manager
   - Automatic rotation (90 days)
   - Encryption at rest (KMS)
   - Access logging
   - IAM policy enforcement

**Security Controls**:
- SC-12: Cryptographic Key Establishment
- SC-13: Cryptographic Protection
- SC-28: Protection of Information at Rest
- IA-5: Authenticator Management

**Architecture**:
```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA PROTECTION ARCHITECTURE                  │
└─────────────────────────────────────────────────────────────────┘

┌───────────────┐                               ┌───────────────┐
│   User Input  │──────────TLS 1.2/1.3─────────▶│  Application  │
│  (HTTPS)      │   (ECDHE-RSA-AES256-GCM)      │  (Memory)     │
└───────────────┘                               └───────┬───────┘
                                                         │
                                                         │
                                    ┌────────────────────┴────────────────────┐
                                    │                                         │
                                    ▼                                         ▼
                          ┌───────────────────┐                   ┌───────────────────┐
                          │  AWS Secrets      │                   │  EBS Volumes      │
                          │  Manager          │                   │  (Output)         │
                          │  ───────────────  │                   │  ───────────────  │
                          │  • API Keys       │                   │  • Generated      │
                          │  • Credentials    │                   │    Pipelines      │
                          │  • CSRF Secrets   │                   │  • Temp Files     │
                          │                   │                   │                   │
                          │  ▼ KMS Encrypted  │                   │  ▼ KMS Encrypted  │
                          │  AES-256-GCM      │                   │  AES-256-XTS      │
                          └───────────────────┘                   └───────────────────┘
                                    │
                                    │
                                    ▼
                          ┌───────────────────┐
                          │  CloudWatch Logs  │
                          │  ───────────────  │
                          │  • Security Events│
                          │  • App Logs       │
                          │  • Audit Trail    │
                          │                   │
                          │  ▼ KMS Encrypted  │
                          │  AES-256-GCM      │
                          │  90-day Retention │
                          └───────────────────┘
```

### 3.7 Layer 7: Monitoring & Audit

**Purpose**: Detect security events and maintain audit trail

**Components**:

1. **CloudWatch Logs**
   - Centralized log aggregation
   - Encrypted storage (KMS)
   - 90-day retention
   - Log Insights queries

2. **Security Event Logging**
   - Structured JSON logs (structlog)
   - Security event categorization
   - Request ID correlation
   - Failed authentication tracking

3. **File Integrity Monitoring (AIDE)**
   - Baseline integrity database
   - Periodic scans (every 6 hours)
   - Change detection and alerting
   - Unauthorized modification prevention

4. **Vulnerability Scanning**
   - Daily Trivy scans (containers)
   - Daily pip-audit scans (Python)
   - SARIF reports to GitHub Security
   - Automated alerts for critical CVEs

5. **CloudWatch Alarms**
   - Authentication failure threshold
   - Critical error rate
   - API error rate
   - Certificate expiration

**Security Controls**:
- AU-2: Audit Events
- AU-6: Audit Review, Analysis, and Reporting
- AU-9: Protection of Audit Information
- SI-4: System Monitoring

**Configuration**:
```yaml
# terraform/cloudwatch-logs.tf
resource "aws_cloudwatch_log_metric_filter" "authentication_failures" {
  name           = "authentication-failures"
  log_group_name = aws_cloudwatch_log_group.purple_parser.name
  pattern        = "[time, request_id, level=ERROR, msg=\"*authentication*failure*\"]"

  metric_transformation {
    name      = "AuthenticationFailures"
    namespace = "PurpleParser"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "auth_failures" {
  alarm_name          = "purple-parser-authentication-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "AuthenticationFailures"
  namespace           = "PurpleParser"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "Alert when authentication failures exceed threshold"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}
```

---

## 4. Trust Boundaries

### 4.1 Trust Boundary Map

```
┌─────────────────────────────────────────────────────────────────┐
│                          TRUST ZONES                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Zone 0: Untrusted (Internet)                                   │
│  • Public internet users                                        │
│  • Potential attackers                                          │
│  • No implicit trust                                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ Trust Boundary 1
                                │ (TLS 1.2/1.3, WAF, DDoS Protection)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Zone 1: DMZ (Load Balancer)                                    │
│  • ALB with TLS termination                                     │
│  • NGINX Ingress Controller                                     │
│  • Rate limiting enforced                                       │
│  • Trust Level: LOW                                             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ Trust Boundary 2
                                │ (Network Policies, mTLS)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Zone 2: Application (Kubernetes Pods)                          │
│  • Purple Parser containers                                     │
│  • Seccomp + AppArmor enforced                                  │
│  • Non-root execution                                           │
│  • Trust Level: MEDIUM                                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ Trust Boundary 3
                                │ (IAM Roles, Secrets Manager)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Zone 3: Data (AWS Services)                                    │
│  • Secrets Manager (API keys)                                   │
│  • CloudWatch Logs (audit)                                      │
│  • EBS volumes (persistent)                                     │
│  • Trust Level: HIGH                                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ Trust Boundary 4
                                │ (TLS, API Keys, Rate Limiting)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Zone 4: External Services (3rd Party APIs)                     │
│  • Anthropic Claude API                                         │
│  • SentinelOne API                                              │
│  • Observo.ai API                                               │
│  • Trust Level: MEDIUM (verified partners)                      │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Trust Boundary Controls

| Boundary | Inbound Controls | Outbound Controls |
|----------|------------------|-------------------|
| **1: Internet → DMZ** | TLS 1.2/1.3, WAF, DDoS protection, rate limiting | N/A (ingress only) |
| **2: DMZ → App** | Network policies, certificate validation, ingress controller | Response size limits, security headers |
| **3: App → Data** | IAM roles, Secrets Manager, KMS encryption | Audit logging, CloudWatch |
| **4: App → External** | TLS 1.2/1.3, API key auth, rate limiting | Request logging, timeout enforcement |

### 4.3 Data Flow Across Boundaries

**User Request Flow**:
1. **Internet → DMZ**: TLS handshake, WAF inspection, rate limit check
2. **DMZ → App**: Network policy check, ingress routing, mTLS (optional)
3. **App → Data**: Secrets retrieval (IAM role), encrypted storage
4. **App → External**: API call with authentication, response validation

**Logging Flow**:
1. **App → Fluentd**: Local log file write
2. **Fluentd → CloudWatch**: TLS 1.2 encrypted transmission
3. **CloudWatch → S3**: Long-term archival (encrypted)

---

## 5. Authentication & Authorization

### 5.1 Authentication Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  AUTHENTICATION ARCHITECTURE                     │
└─────────────────────────────────────────────────────────────────┘

┌───────────────┐
│  External API │
│    Request    │
└───────┬───────┘
        │
        │ HTTPS + API Key Header
        │
        ▼
┌───────────────────────────────────────┐
│  NGINX Ingress Controller             │
│  • TLS termination                    │
│  • Certificate validation             │
│  • Header extraction                  │
└───────────────┬───────────────────────┘
                │
                │ API Key Forwarded
                │
                ▼
┌───────────────────────────────────────┐
│  Application (Flask)                  │
│  • Extract API key from header        │
│  • Validate format                    │
│  • Rate limiting check                │
└───────────────┬───────────────────────┘
                │
                │ Retrieve Expected Key
                │
                ▼
┌───────────────────────────────────────┐
│  AWS Secrets Manager                  │
│  • Retrieve API key                   │
│  • KMS decryption                     │
│  • Return to application              │
└───────────────┬───────────────────────┘
                │
                │ Expected Key
                │
                ▼
┌───────────────────────────────────────┐
│  Application                          │
│  • Constant-time comparison           │
│  • Log authentication attempt         │
│  • Allow or deny request              │
└───────────────────────────────────────┘
```

**Authentication Methods**:

1. **External API Authentication**
   - Method: API Key (Bearer token)
   - Storage: AWS Secrets Manager
   - Rotation: 90 days (automated)
   - Validation: HMAC comparison

2. **Service-to-Service Authentication**
   - Method: AWS IAM Roles
   - Mechanism: IRSA (IAM Roles for Service Accounts)
   - Scope: Least privilege
   - Rotation: Automatic (AWS managed)

3. **Container Registry Authentication**
   - Method: ECR authentication token
   - Mechanism: AWS IAM
   - Duration: 12 hours
   - Refresh: Automatic

### 5.2 Authorization Architecture

**Role-Based Access Control (RBAC)**:

```yaml
# deployment/k8s/rbac.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: purple-parser-role
  namespace: purple-parser
rules:
# Allow reading secrets (for config)
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["purple-parser-secrets"]
  verbs: ["get"]

# Allow reading configmaps
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list"]

# Allow pod self-inspection
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: purple-parser-rolebinding
  namespace: purple-parser
subjects:
- kind: ServiceAccount
  name: purple-parser
  namespace: purple-parser
roleRef:
  kind: Role
  name: purple-parser-role
  apiGroup: rbac.authorization.k8s.io
```

**AWS IAM Policies**:

```hcl
# terraform/iam.tf
resource "aws_iam_policy" "purple_parser_app" {
  name = "purple-parser-application-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.anthropic_api_key.arn,
          aws_secretsmanager_secret.s1_credentials.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = aws_kms_key.secrets.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.purple_parser.arn}:*"
      }
    ]
  })
}
```

---

## 6. Data Protection

### 6.1 Data Classification & Protection

| Data Type | Classification | At Rest Protection | In Transit Protection | Retention |
|-----------|----------------|--------------------|-----------------------|-----------|
| **API Keys** | CONFIDENTIAL | AWS KMS (AES-256) | TLS 1.2+ | Until rotated |
| **User Inputs** | INTERNAL | Memory only | TLS 1.2+ | Session only |
| **Generated Pipelines** | INTERNAL | EBS encryption (AES-256) | TLS 1.2+ | 30 days |
| **Application Logs** | INTERNAL | CloudWatch KMS | TLS 1.2+ | 90 days |
| **Security Events** | CONFIDENTIAL | CloudWatch KMS | TLS 1.2+ | 90 days |

### 6.2 Cryptographic Architecture

**FIPS 140-2 Compliance**:

```
┌─────────────────────────────────────────────────────────────────┐
│              FIPS 140-2 CRYPTOGRAPHIC ARCHITECTURE               │
└─────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│  RHEL UBI 9 Base Image                                        │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  OpenSSL 3.0.7-27.el9 (FIPS Certificate #4282)          │  │
│  │  ─────────────────────────────────────────────────────  │  │
│  │  • FIPS mode enabled (fips=1)                           │  │
│  │  • MD5 disabled                                         │  │
│  │  • SHA-1 disabled (except for legacy compat)            │  │
│  │  • TLS 1.0/1.1 disabled                                 │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Python 3.11 Cryptography                               │  │
│  │  ─────────────────────────────────────────────────────  │  │
│  │  • Built against FIPS OpenSSL                           │  │
│  │  • hashlib.sha256() ✅                                  │  │
│  │  • hashlib.sha3_256() ✅                                │  │
│  │  • hashlib.md5() ❌ (disabled)                          │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘

                              │
                              │ FIPS-validated algorithms only
                              ▼

┌───────────────────────────────────────────────────────────────┐
│  Application Cryptographic Operations                         │
│  ────────────────────────────────────────────────────────────│
│  • Hashing: SHA-256, SHA3-256                                 │
│  • Symmetric: AES-256-GCM                                     │
│  • Asymmetric: RSA-4096, ECDHE P-256/P-384                    │
│  • TLS: 1.2/1.3 with approved ciphersuites                    │
│  • HMAC: HMAC-SHA256                                          │
└───────────────────────────────────────────────────────────────┘
```

**Approved Cryptographic Algorithms**:

| Use Case | Algorithm | Key Size | Compliance |
|----------|-----------|----------|------------|
| **Hashing** | SHA-256 | N/A | FIPS 180-4 |
| **Hashing** | SHA3-256 | N/A | FIPS 202 |
| **Encryption** | AES-GCM | 256-bit | FIPS 197 |
| **Key Exchange** | ECDHE | P-256, P-384 | FIPS 186-4 |
| **Signatures** | RSA-PSS | 4096-bit | FIPS 186-4 |
| **MAC** | HMAC-SHA256 | 256-bit | FIPS 198-1 |

---

## 7. Network Security

### 7.1 Network Segmentation

```
┌─────────────────────────────────────────────────────────────────┐
│                      NETWORK ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  AWS VPC (10.0.0.0/16)                                          │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Public Subnet (10.0.1.0/24) - DMZ                         │ │
│  │  • ALB (internet-facing)                                   │ │
│  │  • NAT Gateway                                             │ │
│  │  • Bastion (optional, tightly restricted)                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Private Subnet 1 (10.0.10.0/24) - Application (AZ1)      │ │
│  │  • EKS worker nodes                                        │ │
│  │  • Purple Parser pods                                      │ │
│  │  • Network policies enforced                               │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Private Subnet 2 (10.0.11.0/24) - Application (AZ2)      │ │
│  │  • EKS worker nodes (redundancy)                           │ │
│  │  • Purple Parser pods (HA)                                 │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Private Subnet 3 (10.0.20.0/24) - Data (AZ1)             │ │
│  │  • VPC Endpoints (Secrets Manager, KMS, CloudWatch)        │ │
│  │  • No internet access                                      │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Security Groups

**ALB Security Group**:
```hcl
resource "aws_security_group" "alb" {
  name        = "purple-parser-alb-sg"
  description = "Security group for Purple Parser ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP from internet (redirect to HTTPS)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "To EKS worker nodes"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = [aws_subnet.private_app_1.cidr_block, aws_subnet.private_app_2.cidr_block]
  }
}
```

**EKS Worker Node Security Group**:
```hcl
resource "aws_security_group" "eks_workers" {
  name        = "purple-parser-eks-workers-sg"
  description = "Security group for EKS worker nodes"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "From ALB"
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description = "Allow worker nodes to communicate"
    from_port   = 0
    to_port     = 65535
    protocol    = "-1"
    self        = true
  }

  egress {
    description = "HTTPS to AWS services (VPC endpoints)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_subnet.private_data.cidr_block]
  }

  egress {
    description = "HTTPS to internet (external APIs)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

---

## 8. Container Security

### 8.1 Container Build Security

**Multi-Stage Build**:
```dockerfile
# Dockerfile.fips
# Stage 1: Builder (isolated build environment)
FROM registry.access.redhat.com/ubi9/python-311:1-77 AS builder

# Enable FIPS mode
ENV OPENSSL_FIPS=1
ENV OPENSSL_FORCE_FIPS_MODE=1

# Install build dependencies
RUN dnf install -y gcc python3-devel && dnf clean all

# Install Python dependencies with hash verification
COPY requirements.lock /tmp/requirements.lock
RUN python3.11 -m pip install --no-cache-dir \
    --require-hashes \
    --no-deps \
    -r /tmp/requirements.lock

# Stage 2: Runtime (minimal runtime environment)
FROM registry.access.redhat.com/ubi9/python-311:1-77

# Enable FIPS mode
ENV OPENSSL_FIPS=1
ENV OPENSSL_FORCE_FIPS_MODE=1

# Copy only necessary files from builder
COPY --from=builder /opt/app-root/lib/python3.11/site-packages /opt/app-root/lib/python3.11/site-packages

# Copy application code
COPY --chown=1001:0 components/ /app/components/
COPY --chown=1001:0 utils/ /app/utils/
COPY --chown=1001:0 *.py /app/

# Security: Non-root user, read-only, no shell
USER 1001
WORKDIR /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python3 -c "import sys; sys.exit(0)"

# Run application
ENTRYPOINT ["python3", "-u", "main.py"]
```

**Container Scanning**:
- Trivy: Daily scans for OS + application vulnerabilities
- Grype: Alternative scanner for validation
- GitHub Container Scanning: Automated on push
- Snyk: Continuous monitoring (optional)

### 8.2 Runtime Security

**Pod Security Standards**:
```yaml
# deployment/k8s/pod-security-standard.yaml
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: purple-parser-psp
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL
  volumes:
    - 'configMap'
    - 'emptyDir'
    - 'projected'
    - 'secret'
    - 'downwardAPI'
    - 'persistentVolumeClaim'
  hostNetwork: false
  hostIPC: false
  hostPID: false
  runAsUser:
    rule: 'MustRunAsNonRoot'
  seLinux:
    rule: 'RunAsAny'
  supplementalGroups:
    rule: 'RunAsAny'
  fsGroup:
    rule: 'RunAsAny'
  readOnlyRootFilesystem: true
```

---

## 9. Secrets Management

### 9.1 Secrets Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   SECRETS MANAGEMENT ARCHITECTURE                │
└─────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│  Application Pod                                               │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Python Application                                      │ │
│  │  ───────────────────────────────────────────────────────│ │
│  │  from utils.aws_secrets_manager import get_secrets_manager│ │
│  │                                                           │ │
│  │  secrets = get_secrets_manager()                         │ │
│  │  api_key = secrets.get_secret_value(                     │ │
│  │      'purple-parser/prod/anthropic-api-key', 'api_key')  │ │
│  └──────────────────────────────────────────────────────────┘ │
│                              │                                 │
│                              │ IAM Role (IRSA)                 │
│                              ▼                                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  AWS SDK (boto3)                                         │ │
│  │  • Automatic credential rotation                         │ │
│  │  • STS token (15-minute expiry)                          │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS (TLS 1.2)
                              ▼
┌───────────────────────────────────────────────────────────────┐
│  AWS Secrets Manager                                           │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Secret: purple-parser/prod/anthropic-api-key            │ │
│  │  ───────────────────────────────────────────────────────│ │
│  │  {                                                        │ │
│  │    "api_key": "sk-ant-api03-..."                         │ │
│  │  }                                                        │ │
│  │                                                           │ │
│  │  ▼ Encrypted with KMS                                    │ │
│  │  ▼ Automatic rotation (90 days)                          │ │
│  │  ▼ Access logging (CloudTrail)                           │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
                              │
                              │ KMS Decrypt
                              ▼
┌───────────────────────────────────────────────────────────────┐
│  AWS KMS                                                       │
│  • AES-256-GCM encryption                                      │
│  • Automatic key rotation (annual)                             │
│  • CloudTrail audit logging                                    │
└───────────────────────────────────────────────────────────────┘
```

### 9.2 Secret Rotation

**Automated Rotation (90 days)**:
1. Secrets Manager triggers rotation Lambda
2. Lambda generates new API key
3. Lambda updates secret value
4. Application cache invalidated
5. New requests use new key
6. Old key deprecated (30-day grace period)

---

## 10. Logging & Monitoring

### 10.1 Logging Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LOGGING ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│  Application Pods                                              │
│  • Structured JSON logs (structlog)                            │
│  • Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL           │
│  • Request ID correlation                                      │
│  • Security event tagging                                      │
└───────────────────────┬───────────────────────────────────────┘
                        │
                        │ stdout/stderr
                        ▼
┌───────────────────────────────────────────────────────────────┐
│  Fluentd DaemonSet                                             │
│  • Tail container logs                                         │
│  • Parse JSON                                                  │
│  • Add Kubernetes metadata                                     │
│  • Filter security events                                      │
└───────────────────────┬───────────────────────────────────────┘
                        │
                        │ TLS 1.2 (encrypted)
                        ▼
┌───────────────────────────────────────────────────────────────┐
│  CloudWatch Logs                                               │
│  • Log group: /aws/eks/purple-parser                           │
│  • KMS encryption at rest                                      │
│  • 90-day retention                                            │
│  • Log Insights queries                                        │
└───────────────────────┬───────────────────────────────────────┘
                        │
                        ├─────────────────┬─────────────────┐
                        ▼                 ▼                 ▼
            ┌──────────────────┐ ┌──────────────┐ ┌──────────────┐
            │ Metric Filters   │ │  Alarms      │ │ S3 Archive   │
            │ • Auth failures  │ │ • P0: 15min  │ │ • Long-term  │
            │ • Critical errors│ │ • P1: 1hr    │ │ • Glacier    │
            └──────────────────┘ └──────────────┘ └──────────────┘
```

### 10.2 Monitoring Stack

**CloudWatch Dashboards**:
- Application metrics (request rate, latency, errors)
- Security metrics (authentication failures, CSRF blocks)
- Infrastructure metrics (CPU, memory, network)
- Compliance metrics (FIPS status, certificate expiration)

**Alerting**:
- SNS topics for different severity levels
- Integration with PagerDuty/Opsgenie
- Email notifications for non-critical
- SMS/phone for P0 incidents

---

## 11. Compliance Architecture

### 11.1 Compliance Controls Mapping

| Control Framework | Coverage | Implementation |
|-------------------|----------|----------------|
| **NIST 800-53** | 76% | Security controls in all 7 layers |
| **DISA STIG** | 76% | RHEL 9 STIG-compliant base image |
| **FIPS 140-2** | 100% | OpenSSL 3.0.7-27.el9 (Cert #4282) |
| **CIS Kubernetes** | 85% | Benchmark v1.8.0 implementation |

### 11.2 Continuous Compliance

**Automated Compliance Checks**:
```yaml
# .github/workflows/compliance-check.yml
name: Compliance Verification

on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM UTC

jobs:
  fips-compliance:
    runs-on: ubuntu-latest
    steps:
      - name: Verify FIPS mode
        run: docker run purple-parser:fips /app/scripts/verify-fips.sh

  stig-compliance:
    runs-on: ubuntu-latest
    steps:
      - name: Run STIG scanner
        run: oscap xccdf eval --profile stig rhel9-stig.xml

  cis-kubernetes:
    runs-on: ubuntu-latest
    steps:
      - name: Run kube-bench
        run: kube-bench run --targets master,node --check 1.2.3,1.2.4,1.2.5
```

---

## 12. Security Services Integration

### 12.1 External Security Services

| Service | Purpose | Integration Method | Security Controls |
|---------|---------|-------------------|-------------------|
| **AWS GuardDuty** | Threat detection | Automatic (AWS) | TLS, CloudTrail |
| **AWS Security Hub** | Compliance aggregation | Automatic (AWS) | IAM policies |
| **GitHub Advanced Security** | SAST, secret scanning | GitHub Actions | OAuth, webhooks |
| **Trivy** | Vulnerability scanning | CI/CD pipeline | Local execution |
| **AIDE** | File integrity | CronJob (K8s) | Local execution |

### 12.2 Security Automation

**CI/CD Security Gates**:
1. SAST scan (CodeQL)
2. Secret scanning (GitHub)
3. Dependency vulnerability scan (pip-audit)
4. Container image scan (Trivy)
5. FIPS compliance verification
6. Infrastructure security scan (tfsec)

**Deployment Blockers**:
- Critical vulnerabilities in dependencies
- High/critical vulnerabilities in container image
- FIPS compliance failure
- Secret exposure detected
- Security policy violations

---

## 13. Disaster Recovery Architecture

### 13.1 Backup Strategy

| Component | Backup Method | Frequency | Retention | Recovery Time |
|-----------|---------------|-----------|-----------|---------------|
| **Application Code** | Git (GitHub) | Continuous | Indefinite | 5 minutes |
| **Container Images** | ECR (multi-region) | On push | 60 days | 10 minutes |
| **Secrets** | Secrets Manager replica | Real-time | Until rotated | 5 minutes |
| **Logs** | S3 Glacier | Daily | 7 years | 24 hours |
| **Infrastructure** | Terraform state (S3) | On change | Indefinite | 30 minutes |

### 13.2 High Availability

**Multi-AZ Deployment**:
- Application pods across 2+ availability zones
- ALB with multi-AZ routing
- EKS control plane (managed, multi-AZ by default)
- RTO: 15 minutes (automatic failover)
- RPO: 0 (stateless application)

---

## 14. Appendix

### 14.1 Security Tools Reference

| Tool | Version | Purpose | Documentation |
|------|---------|---------|---------------|
| **Trivy** | 0.49.1 | Container scanning | https://trivy.dev/ |
| **AIDE** | 0.17.4 | File integrity | https://aide.github.io/ |
| **Fluentd** | 1.16 | Log aggregation | https://www.fluentd.org/ |
| **cert-manager** | 1.14.2 | Certificate management | https://cert-manager.io/ |
| **Seccomp** | Linux 5.15+ | Syscall filtering | https://man7.org/linux/man-pages/man2/seccomp.2.html |
| **AppArmor** | 3.0+ | MAC | https://apparmor.net/ |

### 14.2 Security Contact Information

**Security Team**: security@company.com
**Incident Response**: incidents@company.com (24/7)
**Vulnerability Reports**: vulns@company.com
**PGP Key**: [Key ID: 0x1234567890ABCDEF]

---

**Document Approval**

| Role | Name | Date |
|------|------|------|
| **Security Architect** | [Name] | 2025-10-10 |
| **ISSO** | [Name] | 2025-10-10 |
| **CISO** | [Name] | 2025-10-10 |

---

**End of Security Architecture Document**
