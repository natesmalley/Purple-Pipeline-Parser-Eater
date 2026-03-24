# FedRAMP Compliance Remediation Guide

## Overview

This guide provides step-by-step instructions to remediate all security gaps identified in the Phase 1 deployment infrastructure code and achieve FedRAMP High compliance.

**Current Status**: 60% compliant
**Target Status**: 100% FedRAMP High compliant
**Estimated Timeline**: 2-3 weeks of work

---

## Critical Issues (Must Fix Before Any Federal Deployment)

### 1. Secrets Management Remediation

**Current Problem**:
- Passwords stored in terraform.tfstate (unencrypted)
- Credentials visible in terraform output
- No automatic rotation

**Solution**: Use AWS Secrets Manager (see `secrets-management.tf`)

#### Step-by-Step Fix

**Step 1: Add Secrets Management Configuration**
```bash
# Copy the secure secrets-management.tf file
cp /path/to/secrets-management.tf deployment/aws/terraform/

# Add new variables to variables.tf
cat >> deployment/aws/terraform/variables.tf << 'EOF'

# Add these variables:
variable "rds_master_username" {
  description = "RDS master username (stored in Secrets Manager)"
  type        = string
  default     = "postgres"
  sensitive   = true
}

variable "rds_master_password" {
  description = "RDS master password - WILL BE STORED IN SECRETS MANAGER"
  type        = string
  sensitive   = true
  # Get from: aws secretsmanager get-random-password --password-length 32
}

variable "rds_app_user_password" {
  description = "Application database user password"
  type        = string
  sensitive   = true
}

variable "redis_auth_token" {
  description = "Redis authentication token"
  type        = string
  sensitive   = true
}

variable "use_custom_tls_certificates" {
  description = "Use custom TLS certificates instead of ACM"
  type        = bool
  default     = false
}
EOF
```

**Step 2: Generate Initial Passwords**
```bash
# Generate secure passwords for initial setup
# DO NOT use simple passwords

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Generate RDS master password
RDS_PASSWORD=$(aws secretsmanager get-random-password \
  --password-length 32 \
  --require-each-included-type \
  --query 'RandomPassword' \
  --output text)

# Generate Redis auth token
REDIS_TOKEN=$(aws secretsmanager get-random-password \
  --password-length 32 \
  --query 'RandomPassword' \
  --output text)

# Generate app user password
APP_PASSWORD=$(aws secretsmanager get-random-password \
  --password-length 32 \
  --require-each-included-type \
  --query 'RandomPassword' \
  --output text)

echo "RDS Master Password: $RDS_PASSWORD"
echo "Redis Auth Token: $REDIS_TOKEN"
echo "App User Password: $APP_PASSWORD"
```

**Step 3: Create terraform.tfvars (INITIAL ONLY)**
```hcl
# deployment/aws/terraform/terraform.tfvars
# THIS FILE WILL BE DELETED AFTER INITIAL DEPLOYMENT

aws_region                = "us-east-1"
environment              = "production"
cluster_name             = "purple-pipeline"
kubernetes_version       = "1.27"

# Initial passwords (from Step 2)
rds_master_password      = "YOUR_GENERATED_PASSWORD_HERE"
rds_app_user_password    = "YOUR_GENERATED_PASSWORD_HERE"
redis_auth_token         = "YOUR_GENERATED_TOKEN_HERE"

# Other variables...
```

**Step 4: Deploy with Secrets Management**
```bash
# Initialize Terraform with remote state
terraform init \
  -backend-config="bucket=purple-pipeline-state" \
  -backend-config="key=aws/prod/terraform.tfstate" \
  -backend-config="encrypt=true" \
  -backend-config="dynamodb_table=terraform-locks"

# Plan and review
terraform plan -out=tfplan

# Review the plan carefully - check for secrets
terraform show tfplan | grep -i password || echo "No plaintext passwords in plan"

# Apply
terraform apply tfplan

# Verify secrets are in Secrets Manager
aws secretsmanager list-secrets --region us-east-1
```

**Step 5: DELETE terraform.tfvars Immediately**
```bash
# CRITICAL: Remove passwords from local machine
rm deployment/aws/terraform/terraform.tfvars

# Verify no passwords in git
git status
# Should NOT show terraform.tfvars as modified

# Verify .gitignore protects tfvars
grep "terraform.tfvars" .gitignore
```

**Step 6: Use Secrets in Applications**
```python
# Example: Accessing password from Python application
import boto3
import json

def get_rds_credentials():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(
        SecretId='purple-pipeline/rds/master-password'
    )
    return json.loads(response['SecretString'])

# Usage
creds = get_rds_credentials()
db_password = creds['password']
```

**Verification Checklist**:
- [ ] terraform.tfvars deleted from working directory
- [ ] Secrets Manager shows all secrets created and encrypted
- [ ] CloudTrail logs show Secrets Manager API calls
- [ ] KMS key has rotation enabled
- [ ] No passwords in terraform output
- [ ] No passwords visible in state file: `terraform state show`

---

### 2. Terraform State Encryption

**Current Problem**:
- State backend commented out (using local state)
- Local state not encrypted
- No state locking

**Solution**: Enable remote encrypted state with S3 + DynamoDB

#### Step-by-Step Fix

**Step 1: Create backend.tf**
```hcl
# deployment/aws/terraform/backend.tf
terraform {
  required_version = ">= 1.0"

  # Remote state backend configuration
  backend "s3" {
    bucket            = "purple-pipeline-terraform-state-prod"
    key               = "aws/production/terraform.tfstate"
    region            = "us-east-1"
    encrypt           = true              # MANDATORY
    dynamodb_table    = "terraform-locks"
    workspace_key_prefix = "env"
  }
}
```

**Step 2: Create State Infrastructure**
```bash
# First, apply security-and-encryption.tf to create S3 and DynamoDB
terraform apply -target aws_s3_bucket.terraform_state \
                -target aws_dynamodb_table.terraform_locks

# Verify they're created
aws s3 ls | grep terraform-state
aws dynamodb list-tables | grep terraform-locks
```

**Step 3: Migrate State**
```bash
# Backup current local state
cp terraform.tfstate terraform.tfstate.backup

# Initialize with new remote backend
terraform init -migrate-state

# When asked "Do you want to copy existing state?", answer "yes"

# Verify state is remote
terraform state list  # Should work and show resources
```

**Step 4: Verify Encryption**
```bash
# Check S3 encryption settings
aws s3api get-bucket-encryption \
  --bucket purple-pipeline-terraform-state-prod \
  --region us-east-1

# Check DynamoDB encryption
aws dynamodb describe-table \
  --table-name terraform-locks \
  --region us-east-1 \
  --query 'Table.SSEDescription'

# Verify versioning is enabled
aws s3api get-bucket-versioning \
  --bucket purple-pipeline-terraform-state-prod
```

**Verification Checklist**:
- [ ] S3 bucket encryption enabled with KMS
- [ ] DynamoDB table encryption enabled
- [ ] Versioning enabled on S3 bucket
- [ ] Public access blocked on S3 bucket
- [ ] State locking working (DynamoDB)
- [ ] Local state migrated to remote

---

### 3. CloudTrail Audit Logging

**Current Problem**:
- No CloudTrail configured
- No audit trail of infrastructure changes
- No immutable log storage

**Solution**: Enable CloudTrail with immutable S3 storage (see `security-and-encryption.tf`)

#### Step-by-Step Fix

**Step 1: Deploy CloudTrail Configuration**
```bash
# Apply security-and-encryption.tf
terraform apply -target aws_cloudtrail.main \
                -target aws_s3_bucket.cloudtrail_logs \
                -target aws_cloudwatch_log_group.eks_cluster_logs
```

**Step 2: Verify CloudTrail is Logging**
```bash
# Wait 5 minutes for CloudTrail to start logging
sleep 300

# Check CloudTrail events
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=purple-pipeline \
  --max-items 5 \
  --region us-east-1

# Check S3 for logs
aws s3 ls s3://purple-pipeline-cloudtrail-logs-${AWS_ACCOUNT_ID}/
```

**Step 3: Enable Log File Validation**
```bash
# This is already configured in security-and-encryption.tf
# Verify it's enabled
aws cloudtrail describe-trails \
  --region us-east-1 \
  --query 'trailList[0].{HasCustomEventSelectors: HasCustomEventSelectors, LogFileValidationEnabled: LogFileValidationEnabled}'
```

**Step 4: Set Up CloudWatch Integration**
```bash
# Create CloudWatch Log Group (already done in security-and-encryption.tf)
# Subscribe CloudTrail logs to CloudWatch

aws logs describe-log-groups \
  --log-group-name-prefix /aws/cloudtrail \
  --region us-east-1
```

**Verification Checklist**:
- [ ] CloudTrail trail is logging
- [ ] S3 bucket has immutable storage (WORM) configured
- [ ] Log file validation enabled
- [ ] KMS encryption enabled for logs
- [ ] CloudWatch Logs receiving events
- [ ] EventBridge rules forwarding critical events

---

### 4. TLS/HTTPS Configuration

**Current Problem**:
- No indication of TLS 1.2+ enforcement
- Missing certificate management
- No HTTPS redirect

**Solution**: Configure ALB with TLS 1.2 minimum and automatic certificate renewal

#### Step-by-Step Fix

**Step 1: Create ACM Certificate**
```bash
# Request ACM certificate for your domain
aws acm request-certificate \
  --domain-name example.com \
  --subject-alternative-names www.example.com \
  --validation-method DNS \
  --region us-east-1

# Get certificate ARN
CERT_ARN=$(aws acm list-certificates \
  --region us-east-1 \
  --query 'CertificateSummaryList[0].CertificateArn' \
  --output text)

echo "Certificate ARN: $CERT_ARN"
```

**Step 2: Add to Terraform Configuration**
```hcl
# deployment/aws/terraform/modules/load-balancer/main.tf

# HTTPS listener (TLS 1.2 minimum)
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"  # TLS 1.2 minimum
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
}

# HTTP → HTTPS redirect
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}
```

**Step 3: Add Certificate Variable**
```hcl
# deployment/aws/terraform/variables.tf

variable "certificate_arn" {
  description = "ACM Certificate ARN for HTTPS"
  type        = string
  default     = ""  # Your certificate ARN
}
```

**Step 4: Deploy**
```bash
terraform apply -target aws_lb_listener.https \
                -target aws_lb_listener.http
```

**Step 5: Verify TLS Configuration**
```bash
# Get ALB DNS name
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --region us-east-1 \
  --query 'LoadBalancers[0].DNSName' \
  --output text)

# Test TLS version
openssl s_client -connect ${ALB_DNS}:443 -tls1_2

# Verify minimum TLS 1.2
curl -I --tlsv1.0 https://${ALB_DNS} 2>&1 | grep -i "protocol"
curl -I --tlsv1_1 https://${ALB_DNS} 2>&1 | grep -i "protocol"
curl -I --tlsv1_2 https://${ALB_DNS} 2>&1 | grep -i "success"
```

**Verification Checklist**:
- [ ] ACM certificate created and validated
- [ ] HTTPS listener configured with TLS 1.2
- [ ] HTTP redirects to HTTPS
- [ ] Certificate auto-renewal enabled
- [ ] Only TLS 1.2+ connections accepted
- [ ] Certificate chain complete

---

### 5. Enhanced IAM Policies

**Current Problem**:
- Overly permissive IAM roles
- Missing condition-based access control
- No MFA requirement

**Solution**: Apply least privilege principle with specific conditions

#### Step-by-Step Fix

**Step 1: Review Current IAM Policies**
```bash
# List all custom policies
aws iam list-policies --scope Local --region us-east-1

# Review specific policy
aws iam get-policy-version \
  --policy-arn arn:aws:iam::ACCOUNT:policy/eks-node-policy \
  --version-id v1
```

**Step 2: Implement MFA Requirement**
```hcl
# deployment/aws/terraform/modules/iam-roles/main.tf

# Deny actions without MFA
{
  Sid    = "DenyWithoutMFA"
  Effect = "Deny"
  Action = [
    "iam:*",
    "ec2:TerminateInstances",
    "rds:DeleteDBInstance",
    "s3:DeleteBucket",
    "kms:ScheduleKeyDeletion"
  ]
  Resource = "*"
  Condition = {
    BoolIfExists = {
      "aws:MultiFactorAuthPresent" = "false"
    }
  }
}
```

**Step 3: Add IP Restrictions**
```hcl
# Restrict access to specific IP ranges
Condition = {
  StringLike = {
    "aws:SourceIp" = [
      "10.0.0.0/8",      # Corporate network
      "203.0.113.0/24"   # VPN range
    ]
  }
}
```

**Step 4: Deploy Restricted Policies**
```bash
terraform apply -target module.iam_roles
```

**Verification Checklist**:
- [ ] All principals have specific, limited permissions
- [ ] No wildcards in resource ARNs
- [ ] Conditions restrict access appropriately
- [ ] MFA required for sensitive operations
- [ ] Service-to-service roles don't require MFA
- [ ] Session duration limits enforced (1 hour max for sensitive roles)

---

## High Priority Issues (Must Fix Before Production)

### 6. AWS Config Compliance Monitoring

**Status**: Configuration provided in `security-and-encryption.tf`

**Implementation**:
```bash
terraform apply -target aws_config_configuration_recorder.main \
                -target aws_config_config_rule.required_tags \
                -target aws_config_config_rule.encrypted_volumes
```

---

### 7. GuardDuty Threat Detection

**Status**: Configuration provided in `security-and-encryption.tf`

**Implementation**:
```bash
terraform apply -target aws_guardduty_detector.main \
                -target aws_cloudwatch_event_rule.guardduty_findings
```

---

### 8. VPC Flow Logs

**Status**: Configuration provided in `security-and-encryption.tf`

**Implementation**:
```bash
terraform apply -target aws_flow_log.vpc \
                -target aws_cloudwatch_log_group.vpc_flow_logs
```

---

## Implementation Timeline

### Week 1: Critical Fixes
- [ ] Day 1-2: Secrets Management setup
- [ ] Day 2-3: Terraform state encryption
- [ ] Day 3-4: CloudTrail and audit logging
- [ ] Day 4-5: TLS/HTTPS configuration

### Week 2: High Priority
- [ ] Day 1-2: AWS Config rules
- [ ] Day 2-3: GuardDuty setup
- [ ] Day 3-4: VPC Flow Logs
- [ ] Day 4-5: IAM policy hardening

### Week 3: Validation and Documentation
- [ ] Day 1-2: Security testing
- [ ] Day 2-3: Compliance validation
- [ ] Day 3-4: Documentation updates
- [ ] Day 4-5: FedRAMP assessment readiness

---

## Testing Compliance

### Security Validation Checklist

```bash
#!/bin/bash
# Run security validation tests

# 1. Check encryption
echo "=== Checking Encryption ==="
aws kms list-keys | grep -c kms

# 2. Verify audit logging
echo "=== Checking CloudTrail ==="
aws cloudtrail describe-trails | grep IsLogging

# 3. Check IAM policies
echo "=== Validating IAM ==="
aws iam list-roles | grep -c cluster

# 4. Verify network security
echo "=== Checking Network Policies ==="
kubectl get networkpolicies -A

# 5. Test TLS
echo "=== Testing TLS ==="
openssl s_client -connect load-balancer:443 -tls1_2

# 6. Validate secrets
echo "=== Checking Secrets Manager ==="
aws secretsmanager list-secrets | grep -c purple-pipeline

# 7. Check state encryption
echo "=== Validating State Encryption ==="
aws s3api get-bucket-encryption --bucket terraform-state
```

---

## Documentation Requirements

### Create Following Documentation

1. **Security Architecture Document**
   - Network topology with security groups
   - Encryption key hierarchy
   - IAM role structure
   - Data flow diagrams

2. **Operational Security Procedures**
   - Key rotation procedures
   - Incident response plan
   - Change management process
   - Disaster recovery procedures

3. **Compliance Mapping**
   - NIST 800-53 requirements → Implementation
   - FedRAMP controls → Evidence
   - STIG requirements → Configuration

4. **Risk Assessment Report**
   - Residual risks
   - Mitigation plans
   - Testing results

---

## Post-Remediation Checklist

### Before Federal Deployment

- [ ] All 5 critical issues resolved
- [ ] All 4 high-priority issues implemented
- [ ] Security testing completed
- [ ] Compliance documentation complete
- [ ] FedRAMP control mapping verified
- [ ] Incident response procedures documented
- [ ] Disaster recovery tested
- [ ] Third-party security assessment conducted
- [ ] All vulnerabilities remediated
- [ ] Continuous monitoring in place

### Ongoing Compliance

- [ ] Monthly security audits
- [ ] Quarterly penetration testing
- [ ] Annual FedRAMP assessment
- [ ] Continuous compliance monitoring (AWS Config)
- [ ] Regular vulnerability scans (GuardDuty)
- [ ] Key rotation (automatic, every 30 days)
- [ ] Access reviews (quarterly)
- [ ] Incident logs reviewed (monthly)

---

## Support and Resources

### Key Documentation
- `docs/FEDRAMP-COMPLIANCE-AUDIT.md` - Detailed findings
- `deployment/aws/terraform/secrets-management.tf` - Secrets setup
- `deployment/aws/terraform/security-and-encryption.tf` - Security config

### AWS Resources
- FedRAMP Authorized Services: https://aws.amazon.com/compliance/fedramp/
- AWS Security Best Practices: https://aws.amazon.com/security/best-practices/
- NIST 800-53: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf

### Tools
- tfsec - Terraform security scanning
- Checkov - Infrastructure compliance
- awssecuritymatrix - AWS control mapping

---

## Conclusion

By following this remediation guide, the deployment infrastructure will achieve FedRAMP High compliance within 2-3 weeks. All critical security gaps will be closed, and continuous monitoring will maintain compliance over time.

**Estimated Effort**: 80-120 hours (2-3 person-weeks)
**Compliance Level After Remediation**: FedRAMP High Ready
**Ongoing Compliance Cost**: Monitoring + annual assessment

