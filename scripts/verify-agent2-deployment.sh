#!/bin/bash

################################################################################
# REMEDIATION AGENT 2 - Comprehensive Verification Script
#
# This script verifies all Agent 2 deployments are functional
# Run this after terraform apply completes
#
# Usage: ./verify-agent2-deployment.sh
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Helper functions
print_header() {
  echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
  echo -e "${GREEN}✓ $1${NC}"
  ((PASSED++))
}

print_failure() {
  echo -e "${RED}✗ $1${NC}"
  ((FAILED++))
}

print_warning() {
  echo -e "${YELLOW}⚠ $1${NC}"
  ((WARNINGS++))
}

print_info() {
  echo -e "${BLUE}ℹ $1${NC}"
}

# Main verification
main() {
  print_header "REMEDIATION AGENT 2 - DEPLOYMENT VERIFICATION"
  echo ""
  echo "Verifying CloudTrail, AWS Config, GuardDuty, VPC Flow Logs, and EventBridge"
  echo ""

  # Check AWS credentials
  print_header "AWS Credentials & Configuration"
  if aws sts get-caller-identity > /dev/null 2>&1; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")
    print_success "AWS credentials valid (Account: $ACCOUNT_ID, Region: $REGION)"
  else
    print_failure "AWS credentials not configured"
    exit 1
  fi
  echo ""

  # ============================================================================
  # CLOUDTRAIL VERIFICATION
  # ============================================================================
  print_header "CloudTrail Verification"

  # Find CloudTrail trail
  TRAIL_NAME=$(aws cloudtrail describe-trails --query 'trailList[0].Name' --output text 2>/dev/null || echo "")

  if [ -z "$TRAIL_NAME" ] || [ "$TRAIL_NAME" == "None" ]; then
    print_failure "No CloudTrail trail found"
  else
    print_success "CloudTrail trail found: $TRAIL_NAME"

    # Check if logging is enabled
    LOGGING_STATUS=$(aws cloudtrail get-trail-status --name "$TRAIL_NAME" --query IsLogging --output text 2>/dev/null || echo "unknown")

    if [ "$LOGGING_STATUS" == "True" ] || [ "$LOGGING_STATUS" == "true" ]; then
      print_success "CloudTrail logging is ACTIVE"
    else
      print_failure "CloudTrail logging is NOT active (Status: $LOGGING_STATUS)"
    fi

    # Check S3 bucket
    S3_BUCKET=$(aws cloudtrail describe-trails --trail-name "$TRAIL_NAME" --query 'trailList[0].S3BucketName' --output text 2>/dev/null || echo "")
    if [ -n "$S3_BUCKET" ] && [ "$S3_BUCKET" != "None" ]; then
      print_success "CloudTrail S3 bucket configured: $S3_BUCKET"

      # Check bucket encryption
      ENCRYPTION=$(aws s3api get-bucket-encryption --bucket "$S3_BUCKET" --query 'Rules[0].ApplyServerSideEncryptionByDefault.SSEAlgorithm' --output text 2>/dev/null || echo "")
      if [ "$ENCRYPTION" == "aws:kms" ]; then
        print_success "CloudTrail S3 bucket encrypted with KMS"
      else
        print_warning "CloudTrail S3 bucket encryption not configured or not KMS"
      fi
    else
      print_failure "CloudTrail S3 bucket not configured"
    fi

    # Check log file validation
    LOG_VALIDATION=$(aws cloudtrail describe-trails --trail-name "$TRAIL_NAME" --query 'trailList[0].LogFileValidationEnabled' --output text 2>/dev/null || echo "unknown")
    if [ "$LOG_VALIDATION" == "True" ] || [ "$LOG_VALIDATION" == "true" ]; then
      print_success "CloudTrail log file validation is ENABLED"
    else
      print_warning "CloudTrail log file validation is DISABLED"
    fi

    # Check multi-region
    MULTI_REGION=$(aws cloudtrail describe-trails --trail-name "$TRAIL_NAME" --query 'trailList[0].IsMultiRegionTrail' --output text 2>/dev/null || echo "unknown")
    if [ "$MULTI_REGION" == "True" ] || [ "$MULTI_REGION" == "true" ]; then
      print_success "CloudTrail is configured for MULTI-REGION"
    else
      print_warning "CloudTrail is configured for SINGLE-REGION only"
    fi
  fi
  echo ""

  # ============================================================================
  # AWS CONFIG VERIFICATION
  # ============================================================================
  print_header "AWS Config Verification"

  # Find Config recorder
  RECORDER=$(aws configservice describe-configuration-recorders --query 'ConfigurationRecorders[0].name' --output text 2>/dev/null || echo "")

  if [ -z "$RECORDER" ] || [ "$RECORDER" == "None" ]; then
    print_failure "No AWS Config recorder found"
  else
    print_success "AWS Config recorder found: $RECORDER"

    # Check if recording
    RECORDING=$(aws configservice describe-configuration-recorders --query 'ConfigurationRecorders[0].recording' --output text 2>/dev/null || echo "")
    if [ "$RECORDING" == "True" ] || [ "$RECORDING" == "true" ]; then
      print_success "AWS Config recorder is RECORDING"
    else
      print_failure "AWS Config recorder is NOT recording"
    fi
  fi

  # Count compliance rules
  RULE_COUNT=$(aws configservice describe-config-rules --query 'length(ConfigRules)' --output text 2>/dev/null || echo "0")
  if [ "$RULE_COUNT" -ge 3 ]; then
    print_success "AWS Config compliance rules deployed: $RULE_COUNT rules"
  else
    print_warning "AWS Config has only $RULE_COUNT rules (expected at least 3)"
  fi

  # Check compliance status
  print_info "Compliance status (may take 5-10 minutes to evaluate):"
  aws configservice describe-compliance-by-config-rule \
    --query 'ComplianceByConfigRules[].[ConfigRuleName,Compliance.ComplianceType]' \
    --output table 2>/dev/null || print_warning "Unable to retrieve compliance status"
  echo ""

  # ============================================================================
  # GUARDDUTY VERIFICATION
  # ============================================================================
  print_header "GuardDuty Verification"

  # Find GuardDuty detector
  DETECTOR_ID=$(aws guardduty list-detectors --query 'DetectorIds[0]' --output text 2>/dev/null || echo "")

  if [ -z "$DETECTOR_ID" ] || [ "$DETECTOR_ID" == "None" ]; then
    print_failure "No GuardDuty detector found"
  else
    print_success "GuardDuty detector found: $DETECTOR_ID"

    # Check detector status
    DETECTOR_STATUS=$(aws guardduty get-detector --detector-id "$DETECTOR_ID" --query 'Detector.Status' --output text 2>/dev/null || echo "")
    if [ "$DETECTOR_STATUS" == "ENABLED" ]; then
      print_success "GuardDuty detector is ENABLED"
    else
      print_failure "GuardDuty detector status: $DETECTOR_STATUS"
    fi

    # Check finding publishing frequency
    PUBLISH_FREQ=$(aws guardduty get-detector --detector-id "$DETECTOR_ID" --query 'Detector.FindingPublishingFrequency' --output text 2>/dev/null || echo "")
    print_info "GuardDuty finding publishing frequency: $PUBLISH_FREQ"

    # Check datasources
    EKS_AUDIT=$(aws guardduty get-detector --detector-id "$DETECTOR_ID" --query 'Detector.DataSources.Kubernetes.AuditLogs.Enable' --output text 2>/dev/null || echo "")
    S3_LOGS=$(aws guardduty get-detector --detector-id "$DETECTOR_ID" --query 'Detector.DataSources.S3Logs.Enable' --output text 2>/dev/null || echo "")

    if [ "$EKS_AUDIT" == "True" ] || [ "$EKS_AUDIT" == "true" ]; then
      print_success "GuardDuty EKS audit log monitoring is ENABLED"
    else
      print_warning "GuardDuty EKS audit log monitoring not enabled"
    fi

    if [ "$S3_LOGS" == "True" ] || [ "$S3_LOGS" == "true" ]; then
      print_success "GuardDuty S3 data event monitoring is ENABLED"
    else
      print_warning "GuardDuty S3 data event monitoring not enabled"
    fi
  fi
  echo ""

  # ============================================================================
  # VPC FLOW LOGS VERIFICATION
  # ============================================================================
  print_header "VPC Flow Logs Verification"

  # Find VPC Flow Logs
  FLOW_LOG=$(aws ec2 describe-flow-logs --query 'FlowLogs[0]' --output text 2>/dev/null || echo "")

  if [ -z "$FLOW_LOG" ] || [ "$FLOW_LOG" == "None" ]; then
    print_failure "No VPC Flow Logs found"
  else
    FLOW_LOG_ID=$(aws ec2 describe-flow-logs --query 'FlowLogs[0].FlowLogId' --output text)
    FLOW_LOG_STATUS=$(aws ec2 describe-flow-logs --query 'FlowLogs[0].FlowLogStatus' --output text)
    TRAFFIC_TYPE=$(aws ec2 describe-flow-logs --query 'FlowLogs[0].TrafficType' --output text)

    print_success "VPC Flow Logs found: $FLOW_LOG_ID"

    if [ "$FLOW_LOG_STATUS" == "ACTIVE" ]; then
      print_success "VPC Flow Logs status: ACTIVE"
    else
      print_warning "VPC Flow Logs status: $FLOW_LOG_STATUS"
    fi

    print_info "VPC Flow Logs traffic type: $TRAFFIC_TYPE"

    # Check log group
    LOG_GROUP=$(aws ec2 describe-flow-logs --query 'FlowLogs[0].LogDestinationName' --output text)
    if [ -n "$LOG_GROUP" ]; then
      print_success "VPC Flow Logs CloudWatch log group: $LOG_GROUP"
    fi
  fi
  echo ""

  # ============================================================================
  # EVENTBRIDGE VERIFICATION
  # ============================================================================
  print_header "EventBridge & SNS Verification"

  # Count EventBridge rules
  RULE_COUNT=$(aws events list-rules --query 'length(Rules)' --output text 2>/dev/null || echo "0")
  if [ "$RULE_COUNT" -ge 3 ]; then
    print_success "EventBridge rules deployed: $RULE_COUNT rules"

    # List rules
    print_info "EventBridge rules:"
    aws events list-rules --query 'Rules[*].[Name,State]' --output table
  else
    print_warning "EventBridge has only $RULE_COUNT rules (expected at least 3)"
  fi

  # Check SNS topics
  SNS_COUNT=$(aws sns list-topics --query 'length(Topics)' --output text 2>/dev/null || echo "0")
  if [ "$SNS_COUNT" -gt 0 ]; then
    print_success "SNS topics found: $SNS_COUNT topics"

    # Find security alert topics
    SECURITY_TOPIC=$(aws sns list-topics --query "Topics[?contains(TopicArn, 'security')].TopicArn" --output text 2>/dev/null | head -1 || echo "")
    GUARDDUTY_TOPIC=$(aws sns list-topics --query "Topics[?contains(TopicArn, 'guardduty')].TopicArn" --output text 2>/dev/null | head -1 || echo "")

    if [ -n "$SECURITY_TOPIC" ]; then
      print_success "Security alerts SNS topic: $SECURITY_TOPIC"
    else
      print_warning "Security alerts SNS topic not found"
    fi

    if [ -n "$GUARDDUTY_TOPIC" ]; then
      print_success "GuardDuty alerts SNS topic: $GUARDDUTY_TOPIC"
    else
      print_warning "GuardDuty alerts SNS topic not found"
    fi
  else
    print_warning "No SNS topics found"
  fi
  echo ""

  # ============================================================================
  # SUMMARY & RECOMMENDATIONS
  # ============================================================================
  print_header "Summary"
  echo ""
  echo "Verification Results:"
  echo "  ${GREEN}✓ Passed: $PASSED${NC}"
  echo "  ${YELLOW}⚠ Warnings: $WARNINGS${NC}"
  echo "  ${RED}✗ Failed: $FAILED${NC}"
  echo ""

  if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}DEPLOYMENT VERIFICATION PASSED${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Wait 10-15 minutes for initial logs to appear"
    echo "  2. Verify CloudTrail logs in S3: aws s3 ls s3://purple-pipeline-cloudtrail-logs-${ACCOUNT_ID}/"
    echo "  3. Check AWS Config compliance rules (may take 5-10 minutes)"
    echo "  4. Subscribe to SNS alerts: aws sns subscribe --topic-arn <TOPIC_ARN> --protocol email --notification-endpoint your-email@example.com"
    echo "  5. Monitor GuardDuty findings after 10-30 minutes"
    exit 0
  else
    echo -e "${RED}DEPLOYMENT VERIFICATION FAILED${NC}"
    echo ""
    echo "Issues found: $FAILED"
    echo "Review the failures above and address them before proceeding."
    exit 1
  fi
}

# Run main function
main "$@"
