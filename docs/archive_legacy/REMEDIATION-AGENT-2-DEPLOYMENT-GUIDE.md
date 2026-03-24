# REMEDIATION AGENT 2: Deployment Guide
## Audit Logging, Compliance Monitoring & Threat Detection

**Status**: Configuration Complete, Ready for Deployment
**Date**: November 9, 2025
**FedRAMP Controls**: AU-2, AU-6, AU-12, SI-4

---

## PREPARATION CHECKLIST

Before starting deployments, verify the following:

- [ ] AWS credentials configured in `~/.aws/credentials` or environment variables
- [ ] Terraform >= 1.0 installed and in PATH (`terraform version`)
- [ ] AWS CLI >= 2.0 installed (`aws --version`)
- [ ] jq installed for JSON processing (`jq --version`)
- [ ] Agent 1 (Secrets Management) completed successfully
- [ ] Remote Terraform state configured (S3 + DynamoDB)
- [ ] AWS permissions: CloudTrail, Config, GuardDuty, VPC Flow Logs, EventBridge, SNS, IAM, KMS

---

## PART 1: CONFIGURATION SETUP

### Step 1: Verify Configuration Files

All required configuration has been added to:

1. **variables.tf** - Added 12 new audit logging variables:
   - `enable_cloudtrail` (bool, default: true)
   - `cloudtrail_log_retention_days` (number, default: 2555)
   - `cloudtrail_include_global_events` (bool, default: true)
   - `enable_aws_config` (bool, default: true)
   - `config_max_recording_frequency` (string, default: "CONTINUOUS")
   - `enable_guardduty` (bool, default: true)
   - `guardduty_finding_publishing_frequency` (string, default: "FIFTEEN_MINUTES")
   - `enable_guardduty_eks_audit_logs` (bool, default: true)
   - `enable_guardduty_s3_logs` (bool, default: true)
   - `enable_vpc_flow_logs` (bool, default: true)
   - `vpc_flow_logs_retention_days` (number, default: 90)
   - `vpc_flow_logs_traffic_type` (string, default: "ALL")
   - `vpc_id` (string, default: "")

2. **terraform.tfvars.example** - Added audit logging section with recommended values

3. **security-and-encryption.tf** - Enhanced with:
   - SNS topics for security alerts and GuardDuty alerts
   - EventBridge rules for CloudTrail critical events
   - EventBridge rule for AWS Config compliance violations
   - EventBridge targets with formatted SNS notifications
   - CloudWatch log group for security events

### Step 2: Create terraform.tfvars

```bash
cd deployment/aws/terraform

# Copy the example file
cp terraform.tfvars.example terraform.tfvars

# Edit with your actual VPC ID and region
# IMPORTANT: Set vpc_id to your VPC ID from the VPC module output
# Or get it from your existing VPC:
# aws ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text
```

---

## PART 2: TERRAFORM INIT & VALIDATION

### Step 1: Initialize Terraform

```bash
cd deployment/aws/terraform

# Initialize Terraform (will download required providers)
terraform init

# Expected output:
# - Terraform has been successfully configured!
# - Acquired state lock
# - Successfully copied 1 resource...
```

### Step 2: Validate Configuration

```bash
terraform validate

# Expected output:
# Success! The configuration is valid.
```

### Step 3: Run Terraform Plan

```bash
# Generate plan for review
terraform plan -out=tfplan_agent2

# Review the plan for:
# - CloudTrail resources
# - AWS Config resources
# - GuardDuty detector
# - VPC Flow Logs
# - EventBridge rules
# - SNS topics

# Should show approximately 30-35 resources to be created
```

---

## PART 3: DEPLOYMENT EXECUTION

### Phase 1: CloudTrail Deployment (Task 2)

**Duration**: 5-10 minutes

```bash
# Deploy CloudTrail infrastructure in order:

# Step 1: KMS key for CloudTrail
echo "Step 1: Deploying KMS key for CloudTrail..."
terraform apply -target aws_kms_key.cloudtrail -auto-approve
sleep 10

# Step 2: S3 bucket for logs
echo "Step 2: Deploying S3 bucket..."
terraform apply -target aws_s3_bucket.cloudtrail_logs -auto-approve
sleep 10

# Step 3: S3 versioning
echo "Step 3: Enabling versioning..."
terraform apply -target aws_s3_bucket_versioning.cloudtrail_logs -auto-approve
sleep 5

# Step 4: S3 encryption
echo "Step 4: Configuring encryption..."
terraform apply -target aws_s3_bucket_server_side_encryption_configuration.cloudtrail_logs -auto-approve
sleep 5

# Step 5: S3 bucket policy
echo "Step 5: Applying bucket policy..."
terraform apply -target aws_s3_bucket_policy.cloudtrail_allow_write -auto-approve
sleep 5

# Step 6: CloudTrail resource
echo "Step 6: Creating CloudTrail..."
terraform apply -target aws_cloudtrail.main -auto-approve

echo "CloudTrail deployment complete!"
```

**Verification**:
```bash
# Get CloudTrail name
CLOUDTRAIL_NAME=$(terraform output -raw cloudtrail_bucket 2>/dev/null | sed 's/-cloudtrail-logs.*//')

# Check status
aws cloudtrail describe-trails --trail-name-list "purple-pipeline-trail" \
  --query 'trailList[0].[Name,S3BucketName,IsMultiRegionTrail]' --output table
```

### Phase 2: AWS Config Deployment (Task 3)

**Duration**: 10-15 minutes

```bash
# Deploy AWS Config components:

# Step 1: S3 bucket for Config
echo "Step 1: Creating Config S3 bucket..."
terraform apply -target aws_s3_bucket.config_logs -auto-approve
sleep 10

# Step 2: S3 versioning
echo "Step 2: Enabling S3 versioning..."
terraform apply -target aws_s3_bucket_versioning.config_logs -auto-approve
sleep 5

# Step 3: S3 policy
echo "Step 3: Applying bucket policy..."
terraform apply -target aws_s3_bucket_policy.config_bucket -auto-approve
sleep 5

# Step 4: IAM role for Config
echo "Step 4: Creating IAM role..."
terraform apply -target aws_iam_role.config_role \
               -target aws_iam_role_policy.config_policy \
               -auto-approve
sleep 10

# Step 5: Configuration recorder
echo "Step 5: Creating recorder..."
terraform apply -target aws_config_configuration_recorder.main \
               -target aws_config_configuration_recorder_status.main \
               -auto-approve
sleep 10

# Step 6: Delivery channel
echo "Step 6: Creating delivery channel..."
terraform apply -target aws_config_delivery_channel.main -auto-approve
sleep 10

# Step 7: Deploy compliance rules
echo "Step 7: Deploying compliance rules..."
terraform apply -target aws_config_config_rule.required_tags \
               -target aws_config_config_rule.encrypted_volumes \
               -target aws_config_config_rule.root_account_mfa \
               -auto-approve

echo "AWS Config deployment complete!"
```

**Verification**:
```bash
# Check recorder status
aws configservice describe-configuration-recorders \
  --query 'ConfigurationRecorders[0].[name,recording]' --output table

# List rules
aws configservice describe-config-rules \
  --query 'ConfigRules[*].[ConfigRuleName,ConfigRuleState]' --output table
```

### Phase 3: GuardDuty Deployment (Task 4)

**Duration**: 5 minutes

```bash
# Deploy GuardDuty detector:

echo "Step 1: Enabling GuardDuty detector..."
terraform apply -target aws_guardduty_detector.main -auto-approve

echo "Step 2: Creating GuardDuty findings rule..."
terraform apply -target aws_cloudwatch_event_rule.guardduty_findings -auto-approve

echo "GuardDuty deployment complete!"
```

**Verification**:
```bash
# Get detector ID
DETECTOR_ID=$(terraform output -raw guardduty_detector_id)

# Check status
aws guardduty get-detector --detector-id "${DETECTOR_ID}" \
  --query 'Detector.[Status,FindingPublishingFrequency]' --output table
```

### Phase 4: VPC Flow Logs Deployment (Task 5)

**Duration**: 5 minutes

```bash
# Deploy VPC Flow Logs:

echo "Step 1: Creating IAM role..."
terraform apply -target aws_iam_role.vpc_flow_logs \
               -target aws_iam_role_policy.vpc_flow_logs \
               -auto-approve
sleep 5

echo "Step 2: Creating CloudWatch log group..."
terraform apply -target aws_cloudwatch_log_group.vpc_flow_logs -auto-approve
sleep 5

echo "Step 3: Enabling VPC Flow Logs..."
terraform apply -target aws_flow_log.vpc -auto-approve

echo "VPC Flow Logs deployment complete!"
```

**Verification**:
```bash
# Get VPC Flow Logs details
aws ec2 describe-flow-logs \
  --filter "Name=resource-id,Values=vpc-*" \
  --query 'FlowLogs[0].[FlowLogId,FlowLogStatus,ResourceId]' --output table
```

### Phase 5: EventBridge & SNS Deployment (Task 6)

**Duration**: 10 minutes

```bash
# Deploy alerting infrastructure:

echo "Step 1: Creating SNS topics..."
terraform apply -target aws_sns_topic.security_alerts \
               -target aws_sns_topic.guardduty_alerts \
               -target aws_sns_topic_policy.security_alerts \
               -target aws_sns_topic_policy.guardduty_alerts \
               -auto-approve
sleep 10

echo "Step 2: Creating EventBridge rules..."
terraform apply -target aws_cloudwatch_event_rule.cloudtrail_changes \
               -target aws_cloudwatch_event_rule.config_compliance_change \
               -auto-approve
sleep 5

echo "Step 3: Creating EventBridge targets..."
terraform apply -target aws_cloudwatch_event_target.cloudtrail_changes_sns \
               -target aws_cloudwatch_event_target.config_compliance_sns \
               -target aws_cloudwatch_event_target.guardduty_findings \
               -auto-approve
sleep 5

echo "Step 4: Creating security events log group..."
terraform apply -target aws_cloudwatch_log_group.security_events -auto-approve

echo "EventBridge & SNS deployment complete!"
```

**Verification**:
```bash
# List EventBridge rules
aws events list-rules --query 'Rules[*].[Name,State]' --output table

# Get SNS topic ARNs
terraform output -json | jq '.[] | select(.value | contains("security")) | .value'
```

---

## PART 4: FINAL DEPLOYMENT

### Complete Deployment

To deploy all resources at once (after validation):

```bash
cd deployment/aws/terraform

# Apply all Agent 2 resources
terraform apply tfplan_agent2

# Or apply everything:
terraform apply

# Review changes and type 'yes' to confirm
```

---

## PART 5: VERIFICATION

### Immediate Post-Deployment Verification

```bash
#!/bin/bash
echo "=== AGENT 2 DEPLOYMENT VERIFICATION ==="
echo ""

# 1. CloudTrail Status
echo "1. CloudTrail:"
aws cloudtrail get-trail-status --name purple-pipeline-trail \
  --query '[IsLogging,LatestDeliveryTime]' --output text

# 2. AWS Config Recorder
echo "2. AWS Config:"
aws configservice describe-configuration-recorders \
  --query 'ConfigurationRecorders[0].recording' --output text

# 3. GuardDuty
echo "3. GuardDuty:"
DETECTOR_ID=$(aws guardduty list-detectors --query 'DetectorIds[0]' --output text)
aws guardduty get-detector --detector-id "${DETECTOR_ID}" \
  --query 'Detector.Status' --output text

# 4. VPC Flow Logs
echo "4. VPC Flow Logs:"
aws ec2 describe-flow-logs \
  --query 'FlowLogs[0].FlowLogStatus' --output text

# 5. SNS Topics
echo "5. SNS Topics:"
aws sns list-topics --query 'Topics[*].TopicArn' --output text | grep security

echo ""
echo "=== VERIFICATION COMPLETE ==="
```

### 10-Minute Delayed Verification

Wait 10 minutes for services to initialize, then:

```bash
echo "=== CloudTrail Log Delivery Check ==="
aws s3 ls s3://purple-pipeline-cloudtrail-logs-ACCOUNT-ID/ --recursive | head -10

echo ""
echo "=== AWS Config Rules Evaluation ==="
aws configservice describe-compliance-by-config-rule \
  --query 'ComplianceByConfigRules[].[ConfigRuleName,Compliance.ComplianceType]' \
  --output table
```

---

## PART 6: SUBSCRIBE TO ALERTS

```bash
# Get SNS topic ARNs
SNS_SECURITY=$(aws sns list-topics --query 'Topics[?contains(TopicArn, `security-alerts`)].TopicArn' --output text | head -1)
SNS_GUARDDUTY=$(aws sns list-topics --query 'Topics[?contains(TopicArn, `guardduty-alerts`)].TopicArn' --output text | head -1)

# Subscribe email to alerts
echo "Subscribing to security alerts..."
aws sns subscribe --topic-arn "${SNS_SECURITY}" \
  --protocol email \
  --notification-endpoint your-email@example.com

echo "Subscribing to GuardDuty alerts..."
aws sns subscribe --topic-arn "${SNS_GUARDDUTY}" \
  --protocol email \
  --notification-endpoint your-email@example.com

echo "Check your email for AWS SNS subscription confirmations"
echo "Click the links to activate alerts"
```

---

## TROUBLESHOOTING

### Issue: S3 bucket already exists
**Solution**: S3 bucket names must be globally unique. Terraform will fail if the bucket name is taken. Modify the bucket name or use a random suffix.

### Issue: IAM permissions denied
**Solution**: Ensure your AWS IAM user/role has permissions for:
- `cloudtrail:*`
- `config:*`
- `guardduty:*`
- `ec2:CreateFlowLogs`
- `sns:*`
- `events:*`
- `iam:CreateRole`
- `iam:PutRolePolicy`
- `s3:*`
- `kms:*`

### Issue: CloudTrail logs not appearing
**Solution**: Wait 15-20 minutes for initial logs. CloudTrail requires time to:
1. Enable logging
2. Initialize
3. Deliver logs to S3

### Issue: AWS Config rules not evaluating
**Solution**: Rules may take 5-10 minutes to evaluate. Check status with:
```bash
aws configservice describe-compliance-by-config-rule
```

### Issue: GuardDuty findings not appearing
**Solution**: Findings appear after 10-30 minutes of activity detection. Run test API calls to generate events:
```bash
# This generates CloudTrail events
aws iam list-users

# Check for findings
aws guardduty list-findings --detector-id <DETECTOR_ID>
```

---

## SUCCESS CRITERIA

Deployment is complete when:

- [ ] Terraform apply completes without errors
- [ ] CloudTrail shows IsLogging: true
- [ ] AWS Config recorder shows recording: true
- [ ] GuardDuty detector shows Status: ENABLED
- [ ] VPC Flow Logs shows FlowLogStatus: ACTIVE
- [ ] EventBridge rules visible: `aws events list-rules`
- [ ] SNS topics created: `aws sns list-topics`
- [ ] CloudTrail logs visible in S3 (wait 15 minutes)
- [ ] AWS Config evaluations showing (wait 10 minutes)
- [ ] Email confirmations received for SNS subscriptions

---

## NEXT STEPS

1. **Immediate**: Monitor CloudWatch for initial logs
2. **Daily**: Review compliance findings in AWS Config
3. **Weekly**: Check GuardDuty findings and EventBridge alerts
4. **Monthly**: Archive CloudTrail logs for long-term retention
5. **Quarterly**: Review and update compliance rules

---

## COMPLETION

When all verification checks pass and all resources are deployed:

1. Create completion report: `REMEDIATION-AGENT-2-COMPLETION-REPORT.md`
2. Document any custom configurations
3. Update runbooks with new alerting procedures
4. Proceed to Agent 3 for TLS/HTTPS and IAM hardening

**Expected Total Time**: 1.5-2 hours for complete deployment and verification

---

**Document Version**: 1.0
**Last Updated**: November 9, 2025
**Status**: Ready for Deployment
