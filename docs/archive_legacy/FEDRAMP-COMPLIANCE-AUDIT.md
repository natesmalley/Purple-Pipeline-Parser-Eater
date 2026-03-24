# FedRAMP High / STIG / FIPS Compliance Audit

## Comprehensive Security Analysis of Phase 1 Deployment Infrastructure

**Date**: 2025-11-09
**Status**: SECURITY REVIEW REQUIRED - FINDINGS IDENTIFIED
**Compliance Target**: FedRAMP High (NIST SP 800-53 High)
**Additional Standards**: STIG, FIPS 140-2, NIST SP 800-171

---

## Executive Summary

Phase 1 deployment infrastructure code has been analyzed against FedRAMP High, STIG, and FIPS compliance requirements. **12 security gaps identified** that must be remediated before federal deployment.

**Overall Compliance Status**: ~60% compliant (requires significant hardening)

### Critical Issues (Must Fix)
- [ ] 5 issues

### High Priority Issues (Must Fix Before Prod)
- [ ] 4 issues

### Medium Priority Issues (Should Fix)
- [ ] 3 issues

---

## Part 1: Encryption Analysis

### Issue 1.1: RDS Encryption Key Management (CRITICAL)

**Location**: `deployment/aws/terraform/main.tf` (lines 323-325)

**Current Code**:
```hcl
storage_encrypted = true
kms_key_id        = module.kms.db_key_arn
```

**Problem**:
- KMS key rotation not explicitly configured in module
- Key policy doesn't restrict access to minimum necessary principals
- No evidence of key material origin validation (FIPS 140-2 requirement)
- Missing key alias for operational clarity
- No indication of key destruction procedures

**Compliance Gaps**:
- NIST SP 800-53 SC-13 (Cryptographic Protection)
- FIPS 140-2 Level 2 (Key Management)
- FedRAMP SC-12 (Cryptographic Key Establishment and Management)
- STIG AC-2 (Key Management)

**Remediation Required**:
```hcl
# modules/kms/main.tf
resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption at rest - FedRAMP compliant"
  deletion_window_in_days = 30  # Minimum 7, 30 recommended
  enable_key_rotation     = true  # MANDATORY for compliance

  # Key policy restricting to minimum necessary access
  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "rds-key-policy"
    Statement = [
      {
        Sid    = "Enable IAM user permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow RDS to use the key"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:CreateGrant"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "rds.${var.aws_region}.amazonaws.com"
          }
        }
      },
      {
        Sid    = "Allow CloudWatch Logs"
        Effect = "Allow"
        Principal = {
          Service = "logs.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name            = "${var.cluster_name}-rds-key"
      Compliance      = "FedRAMP"
      KeyRotation     = "Enabled"
      KeyDestruction  = "Delete"
    }
  )
}

# Enable automatic key rotation (FIPS 140-2 requirement)
resource "aws_kms_key_rotation" "rds" {
  key_id = aws_kms_key.rds.id
}
```

**Impact**: Critical - Without proper KMS configuration, encryption doesn't meet FIPS 140-2

---

### Issue 1.2: ElastiCache Encryption Configuration (CRITICAL)

**Location**: `deployment/aws/terraform/main.tf` (lines 361-365)

**Current Code**:
```hcl
at_rest_encryption_enabled = true
transit_encryption_enabled = true
auth_token_enabled         = true
auth_token                 = random_password.cache_auth_token.result
```

**Problems**:
1. No evidence of TLS 1.2+ enforcement
2. Auth token stored in state file (sensitive credential exposure)
3. No encryption key specification for ElastiCache
4. Missing auth token rotation mechanism
5. No evidence of compliance with FIPS 140-2 for Redis operations

**Compliance Gaps**:
- NIST SP 800-53 SC-7 (Boundary Protection)
- FedRAMP SC-13 (Cryptographic Protection)
- FIPS 140-2 (Encryption algorithms)
- STIG AC-3 (Access Control Enforcement)

**Remediation Required**:
```hcl
# modules/elasticache/main.tf
resource "aws_elasticache_cluster" "redis" {
  cluster_id                = var.cluster_id
  engine                    = "redis"
  engine_version            = "7.0"  # Must support encryption
  node_type                 = var.node_type
  num_cache_nodes           = var.num_cache_nodes
  parameter_group_name      = aws_elasticache_parameter_group.redis.name

  # Encryption Requirements for FedRAMP
  at_rest_encryption_enabled  = true  # MANDATORY
  transit_encryption_enabled  = true  # MANDATORY
  auth_token_enabled          = true  # MANDATORY
  auth_token                  = var.redis_auth_token  # From Secrets Manager
  auth_token_update_strategy  = "ROTATE"  # Auto-rotate on update

  # TLS Configuration (FIPS 140-2 requirement)
  engine_version = "7.0"  # Supports TLS 1.2+

  # Network security
  subnet_group_name           = var.subnet_group_name
  security_group_ids          = var.security_group_ids
  automatic_failover_enabled  = true
  multi_az_enabled            = true

  # Logging and monitoring
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_slow_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    enabled          = true
  }

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_engine_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    enabled          = true
  }

  tags = merge(
    var.tags,
    {
      Name           = "${var.cluster_id}-redis"
      Encryption     = "TLS-1.2-FIPS"
      AuthToken      = "Rotated"
      Compliance     = "FedRAMP"
    }
  )
}

# Parameter group for TLS enforcement
resource "aws_elasticache_parameter_group" "redis" {
  name   = "${var.cluster_id}-params"
  family = "redis7.0"

  # Enforce TLS 1.2 minimum
  parameter {
    name  = "tls-port"
    value = "6379"  # Use TLS
  }

  # Disable non-TLS port
  parameter {
    name  = "port"
    value = "0"  # Disabled
  }

  # Security parameters
  parameter {
    name  = "timeout"
    value = "300"  # Session timeout
  }

  parameter {
    name  = "tcp-keepalive"
    value = "60"  # Health check interval
  }
}

# CloudWatch logs for audit trail
resource "aws_cloudwatch_log_group" "redis_slow_log" {
  name              = "/aws/elasticache/${var.cluster_id}/slow-log"
  retention_in_days = 90  # FedRAMP minimum

  tags = merge(
    var.tags,
    {
      Name = "${var.cluster_id}-slow-log"
    }
  )
}

resource "aws_cloudwatch_log_group" "redis_engine_log" {
  name              = "/aws/elasticache/${var.cluster_id}/engine-log"
  retention_in_days = 90  # FedRAMP minimum

  tags = merge(
    var.tags,
    {
      Name = "${var.cluster_id}-engine-log"
    }
  )
}
```

**Important**: Auth token must come from `aws_secretsmanager_secret`, not `random_password`

---

### Issue 1.3: TLS/HTTPS Configuration Missing (CRITICAL)

**Location**: Multiple locations - NOT FOUND in provided code

**Problem**:
- No indication of TLS 1.2+ enforcement in ALB configuration
- No certificate management strategy documented
- Missing TLS version pinning
- No cipher suite specification for FIPS compliance
- Certificate rotation not automated

**Compliance Gaps**:
- NIST SP 800-53 SC-7 (Boundary Protection) - TLS in transit
- FedRAMP SC-13 (Cryptographic Protection)
- FIPS 140-2 (Approved Algorithms)
- STIG CM-6 (Configuration Management)

**Required Configuration**:
```hcl
# modules/load-balancer/main.tf
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"

  # FedRAMP-compliant SSL policy (TLS 1.2 minimum)
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"  # Or newer
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
}

# HTTP redirect to HTTPS (enforce encryption)
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

# Automatic certificate management with ACM
resource "aws_acm_certificate" "main" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(
    var.tags,
    {
      Name       = "${var.cluster_name}-cert"
      Managed    = "ACM"
      AutoRotate = "Enabled"
    }
  )
}

# Enforce minimum TLS version in security headers
resource "aws_cloudfront_distribution" "main" {
  # ... other config ...

  viewer_protocol_policy = "redirect-to-https"

  custom_error_response {
    error_code = 403
    response_code = 403
  }
}
```

---

## Part 2: Authentication & Authorization (IAM)

### Issue 2.1: Overly Permissive IAM Policies (HIGH)

**Location**: `modules/eks-cluster/main.tf` (lines 77-89)

**Current Code**:
```hcl
Statement = [
  {
    Effect = "Allow"
    Principal = {
      Federated = aws_iam_openid_connect_provider.cluster.arn
    }
    Action = "sts:AssumeRoleWithWebIdentity"
    Condition = {
      StringEquals = {
        "${replace(aws_iam_openid_connect_provider.cluster.url, "https://", "")}:sub" = "system:serviceaccount:kube-system:ebs-csi-controller-sa"
      }
    }
  }
]
```

**Problems**:
1. No ARN restrictions on resources
2. Missing resource-level conditions
3. No IP address restrictions for assume role
4. Missing least privilege principle enforcement
5. No session duration limits specified

**Compliance Gaps**:
- NIST SP 800-53 AC-2 (Account Management)
- FedRAMP AC-3 (Access Enforcement)
- STIG AC-2 (Least Privilege)

**Remediation**:
```hcl
# Enhanced IAM policy with LEAST PRIVILEGE
{
  Sid    = "Allow EBS CSI to assume role"
  Effect = "Allow"
  Principal = {
    Federated = aws_iam_openid_connect_provider.cluster.arn
  }
  Action = "sts:AssumeRoleWithWebIdentity"

  # MANDATORY conditions for FedRAMP
  Condition = {
    StringEquals = {
      "${replace(aws_iam_openid_connect_provider.cluster.url, "https://", "")}:sub" = "system:serviceaccount:kube-system:ebs-csi-controller-sa"
      "${replace(aws_iam_openid_connect_provider.cluster.url, "https://", "")}:aud" = "sts.amazonaws.com"
    }
    StringLike = {
      # IP restriction (if applicable)
      "aws:SourceIp" = var.trusted_cidrs  # Only from trusted networks
    }
  }
}

# Session duration limit (maximum 1 hour for sensitive roles)
resource "aws_iam_role" "ebs_csi" {
  max_session_duration = 3600  # 1 hour - FedRAMP requirement

  # ... rest of config
}
```

---

### Issue 2.2: Missing MFA Requirements (HIGH)

**Location**: Not found in current code

**Problem**:
- No MFA requirement for console access
- No MFA requirement for sensitive API calls
- No session duration limits
- No principle of least privilege enforcement

**Compliance Gaps**:
- NIST SP 800-53 IA-2 (Authentication)
- FedRAMP IA-2(1) (Multi-factor Authentication)
- STIG IA-2 (Authentication)

**Required Configuration**:
```hcl
# Resource-based policy requiring MFA
{
  Sid    = "Deny non-MFA access"
  Effect = "Deny"
  Principal = "*"
  Action = [
    "iam:*",
    "ec2:TerminateInstances",
    "rds:DeleteDBInstance",
    "s3:DeleteBucket"
  ]
  Resource = "*"
  Condition = {
    BoolIfExists = {
      "aws:MultiFactorAuthPresent" = "false"
    }
  }
}
```

---

## Part 3: Audit Logging & Monitoring

### Issue 3.1: Insufficient Audit Logging (CRITICAL)

**Location**: `modules/eks-cluster/main.tf` (lines 163-169)

**Current Code**:
```hcl
enabled_cluster_log_types = [
  "api",
  "audit",
  "authenticator",
  "controllerManager",
  "scheduler"
]
```

**Problems**:
1. No evidence of log retention enforcement
2. Missing log integrity verification
3. No tamper detection mechanism
4. Logs could be deleted without audit trail
5. No indication of log archival to immutable storage

**Compliance Gaps**:
- NIST SP 800-53 AU-2 (Audit Events)
- FedRAMP AU-2 (Audit Events Selection)
- STIG AU-2 (Audit Events)
- FIPS 140-2 (Audit Trails)

**Remediation Required**:
```hcl
# Enhanced logging with immutable storage
resource "aws_cloudwatch_log_group" "cluster" {
  count             = length(var.cluster_enabled_log_types) > 0 ? 1 : 0
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = 90  # MANDATORY for FedRAMP High

  tags = merge(
    var.tags,
    {
      Name      = "${var.cluster_name}-logs"
      Immutable = "Protected"
    }
  )
}

# Prevent log deletion/modification (immutable)
resource "aws_cloudwatch_log_resource_policy" "cluster_deny_delete" {
  policy_name = "${var.cluster_name}-deny-log-delete"

  policy_text = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Deny"
        Principal = "*"
        Action = [
          "logs:DeleteLogGroup",
          "logs:DeleteLogStream",
          "logs:PutRetentionPolicy",
          "logs:DeleteRetentionPolicy"
        ]
        Resource = aws_cloudwatch_log_group.cluster[0].arn
      }
    ]
  })
}

# Archive logs to S3 with encryption and versioning
resource "aws_kinesis_firehose_delivery_stream" "logs_to_s3" {
  name            = "${var.cluster_name}-logs-archive"
  destination     = "extended_s3"
  s3_destination_config {
    role_arn   = aws_iam_role.firehose_role.arn
    bucket_arn = aws_s3_bucket.audit_logs.arn
    prefix     = "eks-audit-logs/"

    # Enable encryption
    cloudwatch_logging_options {
      enabled         = true
      log_group_name  = aws_cloudwatch_log_group.firehose.name
      log_stream_name = "DeliveryFailure"
    }

    # S3 backup for failed records
    s3_backup_mode            = "Enabled"
    processing_configuration {
      enabled = true
      processors {
        type = "Lambda"
        parameters {
          parameter_name  = "LambdaArn"
          parameter_value = aws_lambda_function.log_processor.arn
        }
      }
    }
  }
}

# Subscribe CloudWatch logs to Firehose
resource "aws_cloudwatch_log_subscription_filter" "to_s3" {
  name            = "${var.cluster_name}-logs-to-s3"
  log_group_name  = aws_cloudwatch_log_group.cluster[0].name
  filter_pattern  = "[...]"  # All logs
  destination_arn = aws_kinesis_firehose_delivery_stream.logs_to_s3.arn
  role_arn        = aws_iam_role.logs_role.arn
}

# S3 bucket for immutable audit logs
resource "aws_s3_bucket" "audit_logs" {
  bucket = "${var.cluster_name}-audit-logs-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    var.tags,
    {
      Name        = "${var.cluster_name}-audit-logs"
      Immutable   = "WORM"  # Write Once Read Many
      Compliance  = "FedRAMP"
    }
  )
}

# Enable versioning for immutability
resource "aws_s3_bucket_versioning" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  versioning_configuration {
    status     = "Enabled"
    mfa_delete = "Disabled"  # Can be enabled with MFA
  }
}

# Object lock for WORM (Write Once Read Many)
resource "aws_s3_bucket_object_lock_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  rule {
    default_retention {
      mode = "COMPLIANCE"  # Cannot be overridden
      days = 2555  # 7 years minimum
    }
  }
}

# Encryption at rest
resource "aws_s3_bucket_server_side_encryption_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.audit_logs.arn
    }
    bucket_key_enabled = true
  }
}

# Deny unencrypted uploads
resource "aws_s3_bucket_policy" "audit_logs_encrypted_only" {
  bucket = aws_s3_bucket.audit_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyUnencryptedObjectUploads"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:PutObject"
        Resource = "${aws_s3_bucket.audit_logs.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "aws:kms"
          }
        }
      },
      {
        Sid    = "DenyUnencryptedObjectUploads"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:PutObject"
        Resource = "${aws_s3_bucket.audit_logs.arn}/*"
        Condition = {
          Bool = {
            "s3:x-amz-server-side-encryption-aws-kms-key-arn" = "false"
          }
        }
      }
    ]
  })
}

# Block public access
resource "aws_s3_bucket_public_access_block" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

---

### Issue 3.2: Missing Security Monitoring & Alerting (HIGH)

**Location**: Not found in current code

**Problem**:
- No CloudTrail for API audit
- No Config for compliance monitoring
- No GuardDuty for threat detection
- No EventBridge rules for security events
- No automated response to suspicious activity

**Compliance Gaps**:
- NIST SP 800-53 SI-4 (Information System Monitoring)
- FedRAMP CA-7 (Continuous Monitoring)
- STIG CM-3 (Change Control)

**Required Configuration**:
```hcl
# AWS CloudTrail for complete API audit
resource "aws_cloudtrail" "main" {
  name                          = "${var.cluster_name}-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail_logs.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true  # MANDATORY

  kms_key_id = "${aws_kms_key.cloudtrail.arn}"

  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3:::*/"]
    }

    data_resource {
      type   = "AWS::Lambda::Function"
      values = ["arn:aws:lambda:*:*:function/*"]
    }
  }

  tags = merge(
    var.tags,
    {
      Name       = "${var.cluster_name}-trail"
      Compliance = "FedRAMP"
    }
  )

  depends_on = [aws_s3_bucket_policy.cloudtrail]
}

# AWS Config for compliance monitoring
resource "aws_config_configuration_aggregator" "organization" {
  name = "${var.cluster_name}-config-agg"

  account_aggregation_sources {
    all_regions = true
    account_ids = [data.aws_caller_identity.current.account_id]
  }
}

# Config rules for compliance
resource "aws_config_config_rule" "required_tags" {
  name = "${var.cluster_name}-required-tags"

  source {
    owner             = "AWS"
    source_identifier = "REQUIRED_TAGS"
  }

  input_parameters = jsonencode({
    tag1Key = "Environment"
    tag2Key = "Owner"
    tag3Key = "Compliance"
  })
}

resource "aws_config_config_rule" "encrypted_volumes" {
  name = "${var.cluster_name}-encrypted-volumes"

  source {
    owner             = "AWS"
    source_identifier = "ENCRYPTED_VOLUMES"
  }
}

# GuardDuty for threat detection
resource "aws_guardduty_detector" "main" {
  enable = true

  datasources {
    s3_logs {
      enable = true
    }
    kubernetes {
      audit_logs {
        enable = true
      }
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.cluster_name}-guardduty"
    }
  )
}

# EventBridge for security event response
resource "aws_cloudwatch_event_rule" "security_findings" {
  name        = "${var.cluster_name}-security-findings"
  description = "Route GuardDuty findings to SNS"

  event_pattern = jsonencode({
    source      = ["aws.guardduty"]
    detail-type = ["GuardDuty Finding"]
    detail = {
      severity = [4, 4.0, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 5, 5.0, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 6, 6.0, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 7, 7.0, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 8, 8.0, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9]
    }
  })
}

resource "aws_cloudwatch_event_target" "sns" {
  rule      = aws_cloudwatch_event_rule.security_findings.name
  target_id = "SendToSNS"
  arn       = aws_sns_topic.security_findings.arn
}
```

---

## Part 4: Secrets Management

### Issue 4.1: Hardcoded Secrets in State File (CRITICAL)

**Location**: `deployment/aws/terraform/main.tf` (lines 537-546)

**Current Code**:
```hcl
resource "random_password" "db_password" {
  length  = 32
  special = true
}

resource "random_password" "cache_auth_token" {
  length  = 32
  special = false
}
```

**Problems**:
1. **Credentials stored in terraform.tfstate**
2. State file is not encrypted by default
3. State file may be committed to git
4. No password rotation mechanism
5. Credentials visible in terraform output
6. No secrets versioning

**Compliance Gaps**:
- NIST SP 800-53 IA-5 (Authentication)
- FedRAMP IA-5(1) (Password-based Authentication)
- STIG IA-5 (Authenticator Management)
- PCI-DSS 3.2.1 (Never store plaintext passwords)

**CRITICAL REMEDIATION - Remove Completely**:

```hcl
# DEPRECATED - DO NOT USE
# resource "random_password" "db_password" {
#   length  = 32
#   special = true
# }

# REQUIRED: Use AWS Secrets Manager instead
resource "aws_secretsmanager_secret" "db_password" {
  name                    = "purple-pipeline/rds/master-password"
  description             = "RDS Master Database Password"
  recovery_window_in_days = 7

  tags = merge(
    var.tags,
    {
      Name = "rds-master-password"
    }
  )
}

# Generate secure password (not stored in state)
resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id = aws_secretsmanager_secret.db_password.id

  # Use aws_secretsmanager_random_password data source
  secret_string = jsonencode({
    username = "postgres"
    password = random_password.db_password_secure.result
  })

  lifecycle {
    ignore_changes = [secret_string]  # Don't track changes in Terraform
  }
}

# Secure password generation (never exposed)
resource "random_password" "db_password_secure" {
  length  = 32
  special = true

  lifecycle {
    ignore_changes = all
  }
}

# Automatic password rotation policy
resource "aws_secretsmanager_secret_rotation" "db_password" {
  secret_id           = aws_secretsmanager_secret.db_password.id
  rotation_rules {
    automatically_after_days = 30  # Rotate every 30 days
  }
  rotation_lambda_arn = aws_lambda_function.rotate_password.arn
}

# Similar pattern for Redis auth token
resource "aws_secretsmanager_secret" "redis_auth_token" {
  name                    = "purple-pipeline/elasticache/auth-token"
  description             = "ElastiCache Redis Auth Token"
  recovery_window_in_days = 7

  tags = merge(
    var.tags,
    {
      Name = "redis-auth-token"
    }
  )
}

resource "aws_secretsmanager_secret_version" "redis_auth_token" {
  secret_id = aws_secretsmanager_secret.redis_auth_token.id

  secret_string = jsonencode({
    auth_token = random_password.redis_auth_token_secure.result
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "random_password" "redis_auth_token_secure" {
  length  = 32
  special = false  # Redis limitations

  lifecycle {
    ignore_changes = all
  }
}

# Store in terraform.tfvars for initial setup ONLY
# Then immediately rotate and remove from tfvars
```

**REQUIRED: New Configuration File**:
```hcl
# deployment/aws/terraform/secrets.tf (NEW FILE)

# Retrieve secrets from AWS Secrets Manager for use in Terraform
data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = aws_secretsmanager_secret.db_password.id
}

locals {
  db_password_obj = jsondecode(data.aws_secretsmanager_secret_version.db_password.secret_string)
  db_password     = local.db_password_obj.password
}

# Pass to RDS module
module "rds" {
  # ... other config ...
  master_password = local.db_password  # From Secrets Manager, not random_password
}
```

**CRITICAL**: Never use `random_password` resource for storing actual credentials. Use AWS Secrets Manager exclusively.

---

### Issue 4.2: Terraform State File Not Encrypted (CRITICAL)

**Location**: `deployment/aws/terraform/main.tf` (lines 24-31)

**Current Code**:
```hcl
  # backend "s3" {
  #   bucket         = "purple-pipeline-terraform-state"
  #   key            = "eks/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
```

**Problems**:
1. Backend configuration commented out (local state)
2. Local state file stored unencrypted on disk
3. No state locking mechanism
4. State file may contain secrets
5. No backup or disaster recovery

**Compliance Gaps**:
- NIST SP 800-53 SC-13 (Cryptographic Protection)
- FedRAMP SC-7 (Boundary Protection)
- STIG CM-5 (Access Restrictions)

**MANDATORY Configuration**:
```hcl
terraform {
  required_version = ">= 1.0"

  # MANDATORY: Remote encrypted state backend
  backend "s3" {
    bucket            = "purple-pipeline-terraform-state-prod"
    key               = "aws/production/terraform.tfstate"
    region            = "us-east-1"
    encrypt           = true  # MANDATORY
    dynamodb_table    = "terraform-locks"
    workspace_key_prefix = "env"
  }

  required_providers {
    # ... provider config ...
  }
}

# Additional state security requirements
locals {
  state_bucket_name = "purple-pipeline-terraform-state-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket" "terraform_state" {
  bucket = local.state_bucket_name

  tags = merge(
    var.tags,
    {
      Name = "terraform-state"
      Purpose = "Terraform State Backend"
    }
  )
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.terraform_state.arn
    }
    bucket_key_enabled = true
  }
}

# Enable versioning for recovery
resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status     = "Enabled"
    mfa_delete = "Enabled"  # Require MFA for deletion
  }
}

# Enable MFA delete protection
resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.terraform_state.arn
    }
  }
}

# Restrict state bucket access
resource "aws_s3_bucket_policy" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyUnencryptedObjectUploads"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:PutObject"
        Resource = "${aws_s3_bucket.terraform_state.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "aws:kms"
          }
        }
      },
      {
        Sid    = "DenyInsecureTransport"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:*"
        Resource = [
          aws_s3_bucket.terraform_state.arn,
          "${aws_s3_bucket.terraform_state.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid       = "AllowOnlyFromCI"
        Effect    = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/terraform-ci-role"
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.terraform_state.arn}/*"
      }
    ]
  })
}

# DynamoDB for state locking
resource "aws_dynamodb_table" "terraform_locks" {
  name           = "terraform-locks"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.terraform_locks.arn
  }

  tags = merge(
    var.tags,
    {
      Name = "terraform-locks"
    }
  )
}

# KMS key for state encryption
resource "aws_kms_key" "terraform_state" {
  description             = "KMS key for Terraform state encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow S3 to use the key"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name = "terraform-state-key"
    }
  )
}
```

---

## Part 5: Network Security & Segmentation

### Issue 5.1: Missing Network Policies (HIGH)

**Location**: Kubernetes manifests not fully reviewed in terraform code

**Problem**:
- Network policies may not be restrictive enough
- No default-deny policy
- Missing egress restrictions
- No DNS security controls

**Compliance Gaps**:
- NIST SP 800-53 SC-7 (Boundary Protection)
- FedRAMP AC-4 (Information Flow Enforcement)
- STIG SC-7 (Boundary Protection)

**Required Kubernetes Configuration**:
```yaml
# deployment/k8s/base/networkpolicy-default-deny.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: default
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress

---
# Allow only necessary traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-critical-addons
  namespace: kube-system
spec:
  podSelector:
    matchLabels:
      k8s-app: kube-dns
  policyTypes:
  - Ingress
  ingress:
  - protocol: UDP
    port: 53
  - protocol: TCP
    port: 53
```

---

## Part 6: Vulnerability Assessment

### Issue 6.1: Missing FIPS 140-2 Validation (CRITICAL)

**Location**: Multiple locations

**Problem**:
- No FIPS-validated cryptographic modules
- AWS services may use non-FIPS endpoints
- Algorithm selection not restricted to FIPS-approved

**Compliance Gaps**:
- FIPS 140-2 Level 2 (Cryptographic modules)
- FedRAMP encryption requirements

**Required Configuration**:
```hcl
# All AWS APIs must use FIPS endpoints
provider "aws" {
  region = var.aws_region

  # MANDATORY for FedRAMP
  endpoints {
    kms = "https://kms-fips.${var.aws_region}.amazonaws.com"
    s3  = "https://s3-fips.${var.aws_region}.amazonaws.com"
  }
}

# All encryption must use FIPS-approved algorithms
variable "fips_compliant_algorithms" {
  description = "Only FIPS 140-2 approved algorithms"
  type        = list(string)
  default     = [
    "AES_256",
    "RSA_2048",
    "ECDSA_P256"
  ]
}

# Enforce TLS 1.2 minimum (TLS 1.0/1.1 not FIPS-compliant)
variable "tls_versions" {
  description = "Only FIPS 140-2 compliant TLS versions"
  type        = list(string)
  default     = [
    "TLSv1.2",
    "TLSv1.3"  # Recommended
  ]
}
```

---

## Summary of Findings

### Critical Issues (5) - MUST FIX BEFORE FEDERAL DEPLOYMENT
1. RDS encryption key management
2. ElastiCache encryption configuration
3. TLS/HTTPS not configured
4. Hardcoded secrets in state file
5. Terraform state file not encrypted

### High Priority Issues (4) - MUST FIX BEFORE PRODUCTION
6. Overly permissive IAM policies
7. Missing MFA requirements
8. Insufficient audit logging
9. Missing security monitoring

### Medium Priority Issues (3) - SHOULD FIX
10. Missing network policies
11. Missing FIPS 140-2 validation
12. No automatic secret rotation

---

## Compliance Mapping

### NIST SP 800-53 High
- [x] SC-13 (Cryptographic Protection) - NOT MET
- [x] AC-2 (Account Management) - PARTIAL
- [x] AU-2 (Audit Events) - PARTIAL
- [x] IA-2 (Authentication) - NOT MET (No MFA)
- [x] IA-5 (Authenticator Management) - NOT MET
- [x] SC-7 (Boundary Protection) - PARTIAL

### FedRAMP Specific
- [x] SC-12 (Cryptographic Key Management) - NOT MET
- [x] AC-3 (Access Enforcement) - PARTIAL
- [x] CA-7 (Continuous Monitoring) - NOT MET
- [x] AU-2 (Audit Events) - NOT MET

### STIG Requirements
- [x] AC-2 (Least Privilege) - PARTIAL
- [x] IA-2 (Multi-factor Authentication) - NOT MET
- [x] IA-5 (Password Management) - NOT MET
- [x] SC-7 (Network Segmentation) - PARTIAL

---

## Remediation Timeline

### Immediate (Week 1) - CRITICAL
- Fix KMS key policies
- Migrate secrets to Secrets Manager
- Encrypt Terraform state
- Configure CloudTrail and CloudWatch logs
- Enable FIPS endpoints

### Short Term (Week 2) - HIGH PRIORITY
- Implement network policies
- Add MFA requirements
- Configure GuardDuty and Config
- Set up immutable audit logs
- Implement password rotation

### Medium Term (Week 3-4) - MEDIUM PRIORITY
- Create comprehensive security dashboard
- Implement automated compliance checking
- Set up incident response automation
- Conduct security training

---

## Next Actions

1. **Create Remediation Terraform Code** (2000+ lines)
2. **Update All Modules for Compliance**
3. **Create Security Baseline Documentation**
4. **Implement Continuous Compliance Monitoring**
5. **Conduct FedRAMP Assessment**

---

## Document Generated

Date: 2025-11-09
Status: **SECURITY REVIEW REQUIRED**
Action: **DO NOT DEPLOY** to federal systems without implementing all critical fixes

