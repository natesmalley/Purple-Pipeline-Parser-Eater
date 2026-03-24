#!/bin/bash

################################################################################
# REMEDIATION AGENT 2 - Test Events Generator
#
# This script generates test events to verify CloudTrail logging is working
# Run this after CloudTrail deployment to test audit trail capture
#
# Usage: ./generate-test-audit-events.sh
################################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_header() {
  echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
  echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
  echo -e "${BLUE}ℹ $1${NC}"
}

main() {
  print_header "CLOUDTRAIL TEST EVENTS GENERATION"
  echo ""
  echo "This script generates test events to verify CloudTrail is capturing logs"
  echo ""

  # Get AWS account ID
  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
  print_success "AWS Account ID: $ACCOUNT_ID"
  echo ""

  # Test 1: Create test IAM user
  print_header "Test 1: IAM User Creation"
  TEST_USER="cloudtrail-test-user-$(date +%s)"
  echo "Creating test IAM user: $TEST_USER"

  aws iam create-user \
    --user-name "$TEST_USER" \
    --tags Key=Purpose,Value=AuditTrailTest Key=CreatedBy,Value=RemediationAgent2 > /dev/null

  print_success "Created IAM user: $TEST_USER"
  echo ""

  # Test 2: Create access key
  print_header "Test 2: IAM Access Key Creation"
  echo "Creating access key for test user..."

  ACCESS_KEY_OUTPUT=$(aws iam create-access-key --user-name "$TEST_USER")
  ACCESS_KEY_ID=$(echo "$ACCESS_KEY_OUTPUT" | jq -r '.AccessKey.AccessKeyId')

  print_success "Created access key: $ACCESS_KEY_ID (saving for cleanup)"
  echo ""

  # Test 3: Attach policy
  print_header "Test 3: IAM Policy Attachment"
  echo "Attaching ReadOnlyAccess policy..."

  aws iam attach-user-policy \
    --user-name "$TEST_USER" \
    --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess

  print_success "Attached ReadOnlyAccess policy"
  echo ""

  # Test 4: Create S3 bucket (if possible)
  print_header "Test 4: S3 Bucket Creation"
  TEST_BUCKET="audit-test-$(date +%s)-$RANDOM"
  echo "Creating test S3 bucket: $TEST_bucket"

  if aws s3 mb "s3://${TEST_BUCKET}" --region us-east-1 > /dev/null 2>&1; then
    print_success "Created S3 bucket: $TEST_BUCKET"

    # Add test object
    echo "Adding test object to bucket..."
    echo "Test data for CloudTrail verification" | aws s3 cp - "s3://${TEST_BUCKET}/test-object.txt"
    print_success "Added test object to bucket"
  else
    print_info "S3 bucket creation skipped (bucket name may be taken)"
  fi
  echo ""

  # Test 5: Security group modification (if VPC exists)
  print_header "Test 5: Security Group Modification"
  echo "Checking for default VPC..."

  DEFAULT_VPC=$(aws ec2 describe-vpcs \
    --filters Name=isDefault,Values=true \
    --query 'Vpcs[0].VpcId' \
    --output text 2>/dev/null || echo "")

  if [ -n "$DEFAULT_VPC" ] && [ "$DEFAULT_VPC" != "None" ]; then
    echo "Found default VPC: $DEFAULT_VPC"
    echo "Creating test security group..."

    TEST_SG_NAME="test-sg-$(date +%s)"
    SG_ID=$(aws ec2 create-security-group \
      --group-name "$TEST_SG_NAME" \
      --description "Test security group for CloudTrail verification" \
      --vpc-id "$DEFAULT_VPC" \
      --query 'GroupId' \
      --output text)

    print_success "Created security group: $SG_ID"

    # Authorize ingress
    echo "Adding ingress rule..."
    aws ec2 authorize-security-group-ingress \
      --group-id "$SG_ID" \
      --protocol tcp \
      --port 443 \
      --cidr 0.0.0.0/0

    print_success "Added HTTPS ingress rule to security group"
  else
    print_info "No default VPC found, skipping security group test"
  fi
  echo ""

  # Test 6: CloudTrail API calls
  print_header "Test 6: CloudTrail Configuration Queries"
  echo "Querying CloudTrail configuration..."

  TRAIL_COUNT=$(aws cloudtrail describe-trails --query 'length(trailList)' --output text)
  print_success "CloudTrail trails found: $TRAIL_COUNT"

  # List events (this generates a CloudTrail event)
  echo "Querying CloudTrail events (this also generates a CloudTrail event)..."
  RECENT_EVENTS=$(aws cloudtrail lookup-events --max-items 3 --query 'length(Events)' --output text)
  print_success "Recent CloudTrail events: $RECENT_EVENTS"
  echo ""

  # Summary
  print_header "Test Events Generated Successfully"
  echo ""
  echo "The following test events have been created:"
  echo "  1. IAM user creation: $TEST_USER"
  echo "  2. IAM access key creation: $ACCESS_KEY_ID"
  echo "  3. IAM policy attachment (ReadOnlyAccess)"
  if [ -n "$TEST_BUCKET" ]; then
    echo "  4. S3 bucket creation: $TEST_BUCKET"
  fi
  if [ -n "$SG_ID" ]; then
    echo "  5. Security group creation and modification: $SG_ID"
  fi
  echo ""
  echo "CloudTrail should capture these events within 5-15 minutes"
  echo ""

  # Cleanup instructions
  print_info "Cleanup Instructions (run after verification):"
  echo ""
  echo "# Delete test resources:"
  echo "aws iam delete-access-key --user-name $TEST_USER --access-key-id $ACCESS_KEY_ID"
  echo "aws iam detach-user-policy --user-name $TEST_USER --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess"
  echo "aws iam delete-user --user-name $TEST_USER"
  if [ -n "$TEST_BUCKET" ]; then
    echo "aws s3 rb s3://${TEST_BUCKET} --force"
  fi
  if [ -n "$SG_ID" ]; then
    echo "aws ec2 delete-security-group --group-id $SG_ID"
  fi
  echo ""

  # Verification instructions
  print_info "Verification Instructions:"
  echo ""
  echo "1. Wait 5-15 minutes for CloudTrail to deliver logs"
  echo ""
  echo "2. Check CloudTrail lookup events:"
  echo "   aws cloudtrail lookup-events --max-items 10 \\"
  echo "     --query 'Events[*].[EventName,EventTime,Username]' --output table"
  echo ""
  echo "3. Check CloudTrail logs in S3:"
  echo "   aws s3 ls s3://purple-pipeline-cloudtrail-logs-${ACCOUNT_ID}/ --recursive"
  echo ""
  echo "4. Download and examine a log file:"
  echo "   aws s3 cp s3://purple-pipeline-cloudtrail-logs-${ACCOUNT_ID}/<log-path> log.json.gz"
  echo "   gunzip log.json.gz"
  echo "   jq '.Records[] | {EventName, EventSource, SourceIPAddress}' log.json | head -20"
  echo ""
}

# Run main
main "$@"
