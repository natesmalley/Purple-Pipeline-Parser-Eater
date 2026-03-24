#!/bin/bash
################################################################################
# REMEDIATION AGENT 2 - TASK 2 Deployment Script
# Deploy CloudTrail with Multi-Region Logging & Immutable Storage
#
# Prerequisites:
#   - AWS credentials configured
#   - terraform >= 1.0 installed
#   - terraform init already executed
#   - TASK 1 (architecture review) completed
#
# Usage:
#   chmod +x deploy-agent2-cloudtrail.sh
#   ./deploy-agent2-cloudtrail.sh
#
# Estimated Time: 10-15 minutes
################################################################################

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TF_DIR="$PROJECT_ROOT/deployment/aws/terraform"

log_info "Starting CloudTrail Deployment (TASK 2)"
log_info "Project Root: $PROJECT_ROOT"
log_info "Terraform Dir: $TF_DIR"

# Verify prerequisites
if ! command -v terraform &> /dev/null; then
    log_error "terraform not found. Please install Terraform >= 1.0"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    log_error "aws CLI not found. Please install AWS CLI >= 2.0"
    exit 1
fi

log_success "Prerequisites verified"

# Verify AWS credentials
log_info "Verifying AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS credentials not configured. Run: aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)
log_success "AWS Account: $ACCOUNT_ID"
log_success "AWS Region: $REGION"

# Change to terraform directory
cd "$TF_DIR"
log_info "Changed to directory: $TF_DIR"

# Step 1: Plan CloudTrail resources
log_info "Step 1: Planning CloudTrail resources..."
terraform plan \
    -target=aws_kms_key.cloudtrail \
    -target=aws_s3_bucket.cloudtrail_logs \
    -target=aws_s3_bucket_versioning.cloudtrail_logs \
    -target=aws_s3_bucket_server_side_encryption_configuration.cloudtrail_logs \
    -target=aws_s3_bucket_public_access_block.cloudtrail_logs \
    -target=aws_s3_bucket_policy.cloudtrail_allow_write \
    -target=aws_cloudtrail.main \
    -out=cloudtrail.tfplan

log_success "Terraform plan completed"

# Step 2: Deploy KMS key
log_info "Step 2: Deploying KMS key for CloudTrail logs..."
terraform apply \
    -target=aws_kms_key.cloudtrail \
    -auto-approve

KMS_KEY_ID=$(terraform output -raw kms_cloudtrail_key_id 2>/dev/null || echo "unknown")
log_success "KMS key deployed: $KMS_KEY_ID"

# Step 3: Verify KMS key
log_info "Step 3: Verifying KMS key..."
KMS_STATE=$(aws kms describe-key --key-id "$KMS_KEY_ID" --query 'KeyMetadata.KeyState' --output text)
if [ "$KMS_STATE" = "Enabled" ]; then
    log_success "KMS key state: ENABLED"
else
    log_error "KMS key state: $KMS_STATE (expected ENABLED)"
    exit 1
fi

KMS_ROTATION=$(aws kms get-key-rotation-status --key-id "$KMS_KEY_ID" --query 'KeyRotationEnabled' --output text)
log_info "KMS key rotation enabled: $KMS_ROTATION"

# Step 4: Deploy S3 bucket
log_info "Step 4: Deploying S3 bucket for CloudTrail logs..."
terraform apply \
    -target=aws_s3_bucket.cloudtrail_logs \
    -auto-approve

S3_BUCKET=$(terraform output -raw cloudtrail_logs_bucket 2>/dev/null || echo "unknown")
log_success "S3 bucket deployed: $S3_BUCKET"

# Step 5: Enable S3 versioning
log_info "Step 5: Enabling S3 versioning..."
terraform apply \
    -target=aws_s3_bucket_versioning.cloudtrail_logs \
    -auto-approve

VERSIONING=$(aws s3api get-bucket-versioning --bucket "$S3_BUCKET" --query 'Status' --output text)
if [ "$VERSIONING" = "Enabled" ]; then
    log_success "S3 versioning: ENABLED"
else
    log_error "S3 versioning: $VERSIONING (expected Enabled)"
    exit 1
fi

# Step 6: Enable S3 encryption
log_info "Step 6: Enabling S3 encryption with KMS..."
terraform apply \
    -target=aws_s3_bucket_server_side_encryption_configuration.cloudtrail_logs \
    -auto-approve

ENCRYPTION=$(aws s3api get-bucket-encryption --bucket "$S3_BUCKET" --query 'Rules[0].ApplyServerSideEncryptionByDefault.SSEAlgorithm' --output text)
log_success "S3 encryption: $ENCRYPTION"

# Step 7: Block public access
log_info "Step 7: Blocking public access to S3 bucket..."
terraform apply \
    -target=aws_s3_bucket_public_access_block.cloudtrail_logs \
    -auto-approve

log_success "S3 public access blocked"

# Step 8: Apply S3 bucket policy
log_info "Step 8: Applying S3 bucket policy..."
terraform apply \
    -target=aws_s3_bucket_policy.cloudtrail_allow_write \
    -auto-approve

log_success "S3 bucket policy applied"

# Step 9: Deploy CloudTrail
log_info "Step 9: Deploying CloudTrail..."
terraform apply \
    -target=aws_cloudtrail.main \
    -auto-approve

TRAIL_NAME=$(terraform output -raw cloudtrail_name 2>/dev/null || echo "unknown")
log_success "CloudTrail deployed: $TRAIL_NAME"

# Step 10: Start CloudTrail logging
log_info "Step 10: Starting CloudTrail logging..."
aws cloudtrail start-logging --trail-name "$TRAIL_NAME"
log_success "CloudTrail logging started"

# Step 11: Verify CloudTrail status
log_info "Step 11: Verifying CloudTrail status..."
LOGGING=$(aws cloudtrail get-trail-status --name "$TRAIL_NAME" --query 'IsLogging' --output text)
if [ "$LOGGING" = "True" ]; then
    log_success "CloudTrail is actively logging: YES"
else
    log_error "CloudTrail is not logging: $LOGGING"
    exit 1
fi

# Step 12: Verification script
log_info "Step 12: Running comprehensive verification..."

cat > /tmp/verify_cloudtrail_deployment.sh << 'EOF'
#!/bin/bash
set -e

TRAIL_NAME="$1"
S3_BUCKET="$2"
KMS_KEY_ID="$3"

echo "=== CLOUDTRAIL DEPLOYMENT VERIFICATION ==="
echo ""

echo "1. CloudTrail Status:"
TRAIL_STATUS=$(aws cloudtrail get-trail-status --name "$TRAIL_NAME")
echo "   Is Logging: $(echo $TRAIL_STATUS | jq -r '.IsLogging')"
echo "   Latest Delivery Time: $(echo $TRAIL_STATUS | jq -r '.LatestDeliveryTime // "Not yet delivered"')"
echo ""

echo "2. S3 Bucket Configuration:"
echo "   Bucket Name: $S3_BUCKET"
echo "   Versioning: $(aws s3api get-bucket-versioning --bucket "$S3_BUCKET" --query 'Status' --output text)"
echo "   Encryption: $(aws s3api get-bucket-encryption --bucket "$S3_BUCKET" --query 'Rules[0].ApplyServerSideEncryptionByDefault.SSEAlgorithm' --output text)"
echo ""

echo "3. KMS Key Status:"
echo "   Key ID: $KMS_KEY_ID"
echo "   Key State: $(aws kms describe-key --key-id "$KMS_KEY_ID" --query 'KeyMetadata.KeyState' --output text)"
echo "   Key Rotation: $(aws kms get-key-rotation-status --key-id "$KMS_KEY_ID" --query 'KeyRotationEnabled' --output text)"
echo ""

echo "4. CloudTrail Configuration:"
aws cloudtrail describe-trails --trail-name-list "$TRAIL_NAME" \
    --query 'trailList[0].[Name,S3BucketName,IsMultiRegionTrail,EnableLogFileValidation,IncludeGlobalServiceEvents]' \
    --output table
echo ""

echo "5. S3 Log Files (may take 5-15 minutes to appear):"
OBJECT_COUNT=$(aws s3 ls "s3://$S3_BUCKET/" --recursive | wc -l)
if [ $OBJECT_COUNT -gt 0 ]; then
    echo "   Log objects in S3: $OBJECT_COUNT"
    aws s3 ls "s3://$S3_BUCKET/" --recursive | tail -3
else
    echo "   No log files yet - CloudTrail initializing, wait 10-15 minutes"
fi
echo ""

echo "SUMMARY: CloudTrail deployment verification complete!"
EOF

chmod +x /tmp/verify_cloudtrail_deployment.sh
/tmp/verify_cloudtrail_deployment.sh "$TRAIL_NAME" "$S3_BUCKET" "$KMS_KEY_ID"

# Final summary
echo ""
log_success "========================================="
log_success "TASK 2: CloudTrail Deployment COMPLETE"
log_success "========================================="
echo ""
echo "CloudTrail Details:"
echo "├── Trail Name: $TRAIL_NAME"
echo "├── S3 Bucket: $S3_BUCKET"
echo "├── KMS Key: $KMS_KEY_ID"
echo "├── Account ID: $ACCOUNT_ID"
echo "├── Region: $REGION"
echo "└── Status: ACTIVE & LOGGING"
echo ""
echo "Next Steps:"
echo "1. Verify logs appear in S3 (wait 5-15 minutes)"
echo "2. Review logs with: aws s3 ls s3://$S3_BUCKET/ --recursive"
echo "3. Proceed to TASK 3: Deploy AWS Config"
echo ""
log_info "TASK 2 deployment completed successfully!"
