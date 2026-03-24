# Security Runbooks
## Purple Pipeline Parser Eater v9.0.0

**Document Classification**: Internal Use Only
**Last Updated**: 2025-10-10
**Version**: 1.0
**Audience**: Security Team, On-Call Engineers, DevOps

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Daily Operations](#2-daily-operations)
3. [Monitoring & Alerting](#3-monitoring--alerting)
4. [Secret Rotation](#4-secret-rotation)
5. [Certificate Management](#5-certificate-management)
6. [Vulnerability Management](#6-vulnerability-management)
7. [Access Management](#7-access-management)
8. [Backup & Recovery](#8-backup--recovery)
9. [Compliance Operations](#9-compliance-operations)

---

## 1. Introduction

### 1.1 Purpose

This document provides step-by-step operational procedures for maintaining the security posture of Purple Pipeline Parser Eater v9.0.0.

### 1.2 Runbook Usage

- **Prerequisites** listed at the start of each runbook
- **Time estimates** provided for planning
- **Verification steps** included to confirm success
- **Rollback procedures** documented where applicable

### 1.3 Tool Requirements

| Tool | Version | Installation |
|------|---------|--------------|
| `kubectl` | 1.28+ | https://kubernetes.io/docs/tasks/tools/ |
| `aws-cli` | 2.13+ | https://aws.amazon.com/cli/ |
| `docker` | 24.0+ | https://docs.docker.com/get-docker/ |
| `trivy` | 0.49+ | https://aquasecurity.github.io/trivy/ |
| `jq` | 1.6+ | https://stedolan.github.io/jq/download/ |

---

## 2. Daily Operations

### 2.1 Daily Security Health Check

**Frequency**: Every business day
**Duration**: 15 minutes
**Owner**: On-Call Engineer

**Procedure**:

```bash
#!/bin/bash
# Daily Security Health Check Script

echo "🔍 Purple Parser - Daily Security Health Check"
echo "Date: $(date)"
echo "=============================================="

# 1. Check pod health
echo -e "\n1. Pod Health:"
kubectl get pods -n purple-parser
POD_COUNT=$(kubectl get pods -n purple-parser --field-selector=status.phase=Running --no-headers | wc -l)
if [ "$POD_COUNT" -ge 3 ]; then
    echo "✅ All pods running ($POD_COUNT/3)"
else
    echo "⚠️  Only $POD_COUNT pods running (expected 3)"
fi

# 2. Check CloudWatch alarms
echo -e "\n2. CloudWatch Alarms:"
ALARM_COUNT=$(aws cloudwatch describe-alarms --state-value ALARM --query 'MetricAlarms[?contains(AlarmName, `purple-parser`)].AlarmName' --output text | wc -w)
if [ "$ALARM_COUNT" -eq 0 ]; then
    echo "✅ No active alarms"
else
    echo "⚠️  $ALARM_COUNT alarm(s) active:"
    aws cloudwatch describe-alarms --state-value ALARM --query 'MetricAlarms[?contains(AlarmName, `purple-parser`)].AlarmName' --output text
fi

# 3. Check certificate expiration
echo -e "\n3. Certificate Expiration:"
CERT_DAYS=$(kubectl get certificate purple-parser-tls -n purple-parser -o jsonpath='{.status.renewalTime}' | xargs -I {} date -d {} +%s)
CURRENT=$(date +%s)
DAYS_REMAINING=$(( ($CERT_DAYS - $CURRENT) / 86400 ))
if [ "$DAYS_REMAINING" -gt 30 ]; then
    echo "✅ Certificate valid for $DAYS_REMAINING days"
else
    echo "⚠️  Certificate expires in $DAYS_REMAINING days (renewal needed)"
fi

# 4. Check recent security events
echo -e "\n4. Recent Security Events (last 24h):"
SECURITY_EVENTS=$(aws logs filter-log-events \
    --log-group-name /aws/eks/purple-parser \
    --start-time $(($(date +%s) - 86400))000 \
    --filter-pattern "CRITICAL" \
    --query 'events[*].message' --output text | wc -l)
if [ "$SECURITY_EVENTS" -eq 0 ]; then
    echo "✅ No critical security events"
else
    echo "⚠️  $SECURITY_EVENTS critical event(s) detected"
fi

# 5. Check AIDE integrity
echo -e "\n5. File Integrity (AIDE):"
AIDE_JOB=$(kubectl get job -n purple-parser -l app=aide-check --sort-by=.metadata.creationTimestamp | tail -1 | awk '{print $1}')
if [ -n "$AIDE_JOB" ]; then
    AIDE_STATUS=$(kubectl get job $AIDE_JOB -n purple-parser -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}')
    if [ "$AIDE_STATUS" = "True" ]; then
        echo "✅ AIDE check passed (last run: $AIDE_JOB)"
    else
        echo "⚠️  AIDE check failed or in progress"
    fi
else
    echo "⚠️  No recent AIDE jobs found"
fi

# 6. Check vulnerability scan results
echo -e "\n6. Vulnerability Scan Results:"
TRIVY_JOB=$(kubectl get job -n purple-parser -l app=trivy-scan --sort-by=.metadata.creationTimestamp | tail -1 | awk '{print $1}')
if [ -n "$TRIVY_JOB" ]; then
    TRIVY_STATUS=$(kubectl get job $TRIVY_JOB -n purple-parser -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}')
    if [ "$TRIVY_STATUS" = "True" ]; then
        echo "✅ Trivy scan completed (last run: $TRIVY_JOB)"
    else
        echo "⚠️  Trivy scan failed or in progress"
    fi
else
    echo "⚠️  No recent Trivy scan jobs found"
fi

# 7. Summary
echo -e "\n=============================================="
echo "Daily Health Check Complete"
echo "Report any ⚠️  warnings to #security-incidents"
```

**Expected Output**:
- All checks show ✅ (green checkmarks)
- Any ⚠️  (warnings) require investigation

**Escalation**:
- 0 warnings: No action required
- 1-2 warnings: Investigate and document findings
- 3+ warnings: Escalate to Security Team Lead

---

### 2.2 Weekly Security Review

**Frequency**: Every Monday 10:00 AM
**Duration**: 30 minutes
**Owner**: Security Team Lead

**Agenda**:
1. Review previous week's security events
2. Review vulnerability scan reports
3. Review access logs for anomalies
4. Check compliance dashboard
5. Review pending security updates

**Procedure**:

```bash
# Weekly Security Review Report

# 1. Security events summary
echo "📊 Weekly Security Events (last 7 days)"
aws logs start-query \
    --log-group-name /aws/eks/purple-parser \
    --start-time $(($(date +%s) - 604800)) \
    --end-time $(date +%s) \
    --query-string 'fields @timestamp, level, message
    | filter level in ["ERROR", "CRITICAL"]
    | stats count() by level'

# 2. Authentication failures
echo -e "\n🔐 Authentication Failures (last 7 days)"
aws logs start-query \
    --log-group-name /aws/eks/purple-parser \
    --start-time $(($(date +%s) - 604800)) \
    --end-time $(date +%s) \
    --query-string 'fields @timestamp, message
    | filter message like /authentication.*fail/
    | stats count() by bin(1d)'

# 3. API usage statistics
echo -e "\n📈 API Usage Statistics"
aws cloudwatch get-metric-statistics \
    --namespace PurpleParser \
    --metric-name APICallCount \
    --start-time $(date -d '7 days ago' --iso-8601) \
    --end-time $(date --iso-8601) \
    --period 86400 \
    --statistics Sum

# 4. Vulnerability scan summary
echo -e "\n🔍 Vulnerability Scan Summary"
kubectl logs -n purple-parser job/trivy-vulnerability-scan-$(date +%Y%m%d) | \
    grep -E "Total:|CRITICAL:|HIGH:" || echo "No recent scan results"

# 5. CloudTrail activity (sensitive operations)
echo -e "\n🔑 Sensitive AWS Operations (last 7 days)"
aws cloudtrail lookup-events \
    --lookup-attributes AttributeKey=EventName,AttributeValue=RotateSecret \
    --start-time $(date -d '7 days ago' --iso-8601) \
    --query 'Events[*].[EventTime,Username,EventName]' \
    --output table
```

**Action Items**:
- Document any concerning trends
- Create tickets for follow-up investigations
- Update threat model if new threats identified

---

## 3. Monitoring & Alerting

### 3.1 CloudWatch Alarm Investigation

**Trigger**: CloudWatch Alarm notification received
**Duration**: 10-30 minutes
**Owner**: On-Call Engineer

**Procedure**:

```bash
# CloudWatch Alarm Investigation

# 1. Get alarm details
export ALARM_NAME="purple-parser-authentication-failures"

aws cloudwatch describe-alarms \
    --alarm-names $ALARM_NAME \
    --output table

# 2. Check alarm history
aws cloudwatch describe-alarm-history \
    --alarm-name $ALARM_NAME \
    --history-item-type StateUpdate \
    --max-records 10

# 3. Get metric data for the alarm period
aws cloudwatch get-metric-statistics \
    --namespace PurpleParser \
    --metric-name AuthenticationFailures \
    --start-time $(date -d '1 hour ago' --iso-8601) \
    --end-time $(date --iso-8601) \
    --period 300 \
    --statistics Sum,Average,Maximum

# 4. Query logs for related events
aws logs start-query \
    --log-group-name /aws/eks/purple-parser \
    --start-time $(($(date +%s) - 3600))000 \
    --end-time $(date +%s)000 \
    --query-string 'fields @timestamp, level, message, request_id
    | filter message like /authentication.*fail/
    | sort @timestamp desc
    | limit 20'

# Wait for query to complete
QUERY_ID=$(aws logs start-query ... --output text)
sleep 5
aws logs get-query-results --query-id $QUERY_ID

# 5. Check for patterns
# - Single IP with many failures → Brute force attack
# - Multiple IPs, distributed → Credential stuffing
# - After deployment → Configuration issue
# - Regular intervals → Automated scanner

# 6. Take action based on findings
# If brute force:
#   - Block IP at WAF
#   - Rotate API keys if compromised
# If config issue:
#   - Rollback deployment
#   - Fix configuration
# If scanner:
#   - Update WAF rules
#   - No immediate action if blocked
```

**Decision Tree**:

```
Alarm Triggered
    │
    ├─ False Positive? → Tune alarm threshold → Close ticket
    │
    ├─ Configuration Issue? → Rollback/Fix → Verify → Close ticket
    │
    ├─ Attack in Progress? → Follow Incident Response Plan → Escalate
    │
    └─ Suspicious Activity? → Investigate further → Document findings
```

---

### 3.2 AIDE File Integrity Alert

**Trigger**: AIDE detects file changes
**Duration**: 20-60 minutes
**Owner**: Security Engineer

**Procedure**:

```bash
# AIDE File Integrity Investigation

# 1. Get AIDE job logs
AIDE_JOB=$(kubectl get job -n purple-parser -l app=aide-check --sort-by=.metadata.creationTimestamp | tail -1 | awk '{print $1}')
kubectl logs job/$AIDE_JOB -n purple-parser > aide-report.txt

# 2. Parse AIDE report
cat aide-report.txt | grep -A 10 "^Changed:"
cat aide-report.txt | grep -A 10 "^Added:"
cat aide-report.txt | grep -A 10 "^Removed:"

# 3. Identify changed files
CHANGED_FILES=$(cat aide-report.txt | awk '/^Changed:/{flag=1;next}/^Added:|^Removed:/{flag=0}flag')

# 4. Investigate each changed file
for file in $CHANGED_FILES; do
    echo "Investigating: $file"

    # Check git history (for tracked files)
    if git ls-files --error-unmatch "$file" 2>/dev/null; then
        git log -1 --oneline "$file"
    fi

    # Check recent deployments
    kubectl rollout history deployment/purple-parser -n purple-parser

    # Check file metadata
    kubectl exec deployment/purple-parser -n purple-parser -- stat "$file"
done

# 5. Determine legitimacy
# Legitimate changes:
#   - Recent deployment (within last 24h)
#   - Known configuration update
#   - Automatic updates (e.g., cache files)
#
# Suspicious changes:
#   - No recent deployment
#   - System files modified (/etc, /usr/bin)
#   - Unexpected binary changes

# 6. Take action
# If legitimate:
#   - Update AIDE baseline
kubectl exec deployment/purple-parser -n purple-parser -- aide --init
kubectl exec deployment/purple-parser -n purple-parser -- \
    mv /var/lib/aide/aide.db.new /var/lib/aide/aide.db

# If suspicious:
#   - Follow Incident Response Plan (Container Compromise)
#   - Isolate affected pods
#   - Collect forensic evidence
#   - Escalate to Security Team Lead
```

**Legitimate Change Examples**:
- `/app/output/` - Generated parser files (expected)
- `/var/log/` - Application logs (expected)
- `/tmp/` - Temporary files (expected, but not monitored)

**Suspicious Change Examples**:
- `/app/main.py` - Core application code (NOT expected)
- `/usr/bin/python3` - System binaries (NOT expected)
- `/etc/passwd` - System configuration (NOT expected)

---

## 4. Secret Rotation

### 4.1 Routine API Key Rotation (90-day cycle)

**Frequency**: Every 90 days
**Duration**: 45 minutes
**Owner**: Security Team
**Downtime**: None (rolling restart)

**Procedure**:

```bash
#!/bin/bash
# API Key Rotation Script
# Run every 90 days

set -e

echo "🔑 API Key Rotation - Purple Pipeline Parser"
echo "Date: $(date)"
echo "=============================================="

# 1. Pre-rotation checks
echo -e "\n1. Pre-rotation checks..."

# Check current secret age
LAST_ROTATION=$(aws secretsmanager describe-secret \
    --secret-id purple-parser/prod/anthropic-api-key \
    --query 'LastRotatedDate' --output text)
echo "Last rotation: $LAST_ROTATION"

# Verify application is healthy
POD_COUNT=$(kubectl get pods -n purple-parser --field-selector=status.phase=Running --no-headers | wc -l)
if [ "$POD_COUNT" -lt 3 ]; then
    echo "❌ Application not healthy (only $POD_COUNT pods running)"
    exit 1
fi
echo "✅ Application healthy ($POD_COUNT pods)"

# 2. Generate new API key
echo -e "\n2. Generating new API key..."
echo "⚠️  MANUAL STEP: Generate new API key in Anthropic Console"
echo "   1. Go to https://console.anthropic.com/settings/keys"
echo "   2. Create new API key with name: purple-parser-$(date +%Y%m%d)"
echo "   3. Copy the key (sk-ant-api03-...)"
read -p "   4. Press Enter when ready to continue..."
read -sp "   5. Paste new API key: " NEW_API_KEY
echo ""

# Validate API key format
if [[ ! "$NEW_API_KEY" =~ ^sk-ant-api03- ]]; then
    echo "❌ Invalid API key format"
    exit 1
fi
echo "✅ API key format validated"

# 3. Test new API key
echo -e "\n3. Testing new API key..."
TEST_RESPONSE=$(curl -s -X POST https://api.anthropic.com/v1/messages \
    -H "x-api-key: $NEW_API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -H "content-type: application/json" \
    -d '{
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 10,
        "messages": [{"role": "user", "content": "test"}]
    }')

if echo "$TEST_RESPONSE" | jq -e '.content' > /dev/null; then
    echo "✅ New API key works"
else
    echo "❌ New API key test failed"
    echo "$TEST_RESPONSE"
    exit 1
fi

# 4. Update AWS Secrets Manager
echo -e "\n4. Updating AWS Secrets Manager..."
aws secretsmanager put-secret-value \
    --secret-id purple-parser/prod/anthropic-api-key \
    --secret-string "{\"api_key\":\"$NEW_API_KEY\",\"rotated_at\":\"$(date --iso-8601)\"}"
echo "✅ Secret updated in AWS Secrets Manager"

# 5. Rolling restart of pods
echo -e "\n5. Performing rolling restart..."
kubectl rollout restart deployment/purple-parser -n purple-parser
kubectl rollout status deployment/purple-parser -n purple-parser --timeout=5m
echo "✅ Pods restarted with new API key"

# 6. Verify new key in use
echo -e "\n6. Verifying new API key in use..."
sleep 30  # Wait for pods to pick up new key
kubectl logs deployment/purple-parser -n purple-parser --tail=10 | grep -q "Successfully loaded secrets" && echo "✅ New key loaded" || echo "⚠️  Check logs manually"

# 7. Revoke old API key
echo -e "\n7. Revoking old API key..."
echo "⚠️  MANUAL STEP: Revoke old API key in Anthropic Console"
echo "   1. Go to https://console.anthropic.com/settings/keys"
echo "   2. Find old key (created before $(date +%Y%m%d))"
echo "   3. Click 'Delete' button"
read -p "   4. Press Enter when completed..."
echo "✅ Old key revoked"

# 8. Post-rotation verification
echo -e "\n8. Post-rotation verification..."

# Check application health
POD_COUNT=$(kubectl get pods -n purple-parser --field-selector=status.phase=Running --no-headers | wc -l)
if [ "$POD_COUNT" -ge 3 ]; then
    echo "✅ All pods healthy ($POD_COUNT/3)"
else
    echo "❌ Only $POD_COUNT pods healthy - investigate!"
    exit 1
fi

# Test API endpoint
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" https://parser.your-domain.com/health)
if [ "$HEALTH_CHECK" = "200" ]; then
    echo "✅ API health check passed"
else
    echo "❌ API health check failed (HTTP $HEALTH_CHECK)"
    exit 1
fi

# 9. Update documentation
echo -e "\n9. Documentation..."
echo "✅ Record rotation in change log"
echo "   Date: $(date --iso-8601)"
echo "   Secret: purple-parser/prod/anthropic-api-key"
echo "   Rotated by: $(whoami)"

# 10. Schedule next rotation
NEXT_ROTATION=$(date -d '+90 days' +%Y-%m-%d)
echo -e "\n✅ Rotation complete!"
echo "Next rotation due: $NEXT_ROTATION"
echo "Set calendar reminder for: $(date -d '+85 days' +%Y-%m-%d)"
```

**Verification**:
- [ ] New API key generated successfully
- [ ] New API key tested and working
- [ ] Secret updated in AWS Secrets Manager
- [ ] Pods restarted without errors
- [ ] Application processing requests normally
- [ ] Old API key revoked
- [ ] Next rotation scheduled

**Rollback** (if issues occur):
```bash
# Revert to previous secret version
aws secretsmanager get-secret-value \
    --secret-id purple-parser/prod/anthropic-api-key \
    --version-stage AWSPREVIOUS \
    --query 'SecretString' --output text | \
    aws secretsmanager put-secret-value \
        --secret-id purple-parser/prod/anthropic-api-key \
        --secret-string file:///dev/stdin

# Restart pods to pick up old key
kubectl rollout restart deployment/purple-parser -n purple-parser
```

---

### 4.2 Emergency API Key Rotation (Compromise)

**Trigger**: API key compromise suspected or confirmed
**Duration**: 10 minutes
**Owner**: On-Call Engineer
**Downtime**: ~2 minutes (brief service disruption acceptable)

**Procedure**:

```bash
#!/bin/bash
# EMERGENCY API Key Rotation
# Use when API key is compromised

set -e

echo "🚨 EMERGENCY API KEY ROTATION 🚨"
echo "Incident ID: INC-$(date +%Y%m%d-%H%M%S)"

# 1. IMMEDIATE REVOCATION - Invalidate current key
echo "1. Invalidating compromised key..."
aws secretsmanager put-secret-value \
    --secret-id purple-parser/prod/anthropic-api-key \
    --secret-string '{"api_key":"REVOKED-COMPROMISED"}'

# 2. Restart pods to stop using old key
echo "2. Restarting pods (blocks further API usage)..."
kubectl delete pods -n purple-parser -l app=purple-parser --force --grace-period=0

# 3. Generate new key ASAP
echo "3. Generate new API key NOW:"
echo "   Go to: https://console.anthropic.com/settings/keys"
read -sp "   Paste new key: " NEW_KEY
echo ""

# 4. Update secret
aws secretsmanager put-secret-value \
    --secret-id purple-parser/prod/anthropic-api-key \
    --secret-string "{\"api_key\":\"$NEW_KEY\",\"emergency_rotation\":\"$(date --iso-8601)\"}"

# 5. Verify recovery
kubectl wait --for=condition=ready pod -l app=purple-parser -n purple-parser --timeout=2m
echo "✅ Service recovered"

# 6. Notify stakeholders
echo "⚠️  NOTIFY: Incident declared, API key rotated"

# 7. Initiate investigation
echo "⚠️  BEGIN INVESTIGATION: How was key compromised?"
```

**Follow-up Actions**:
- Start formal incident investigation
- Review CloudTrail logs for unauthorized access
- Check application logs for API key exposure
- Review all systems with access to secrets
- Update post-incident report

---

## 5. Certificate Management

### 5.1 Certificate Renewal Verification

**Frequency**: Weekly (Mondays)
**Duration**: 5 minutes
**Owner**: On-Call Engineer

**Procedure**:

```bash
# Certificate Status Check

# 1. Check certificate expiration
kubectl get certificate -n purple-parser

# 2. Get detailed certificate info
kubectl describe certificate purple-parser-tls -n purple-parser

# 3. Check TLS secret
kubectl get secret purple-parser-tls -n purple-parser -o jsonpath='{.data.tls\.crt}' | \
    base64 -d | \
    openssl x509 -noout -dates -subject -issuer

# 4. Verify cert-manager is running
kubectl get pods -n cert-manager

# 5. Check certificate renewal history
kubectl get certificaterequest -n purple-parser --sort-by=.metadata.creationTimestamp

# Expected output:
# - Certificate status: Ready=True
# - Expiration: >30 days away
# - Issuer: Let's Encrypt
```

**Red Flags**:
- Certificate expires in <30 days
- Certificate status: Ready=False
- cert-manager pods not running
- Recent failed renewal attempts

**Action**: If any red flags, follow certificate renewal procedure immediately

---

### 5.2 Manual Certificate Renewal

**Trigger**: Certificate near expiration or renewal failed
**Duration**: 15 minutes
**Owner**: DevOps Engineer

**Procedure**:

```bash
#!/bin/bash
# Manual Certificate Renewal

# 1. Check current certificate status
kubectl describe certificate purple-parser-tls -n purple-parser

# 2. Delete certificate to trigger renewal
kubectl delete certificate purple-parser-tls -n purple-parser

# 3. Recreate certificate resource
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: purple-parser-tls
  namespace: purple-parser
spec:
  secretName: purple-parser-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - parser.your-domain.com
  duration: 2160h  # 90 days
  renewBefore: 720h  # 30 days
  privateKey:
    algorithm: RSA
    size: 4096
EOF

# 4. Monitor certificate issuance
kubectl get certificaterequest -n purple-parser -w

# Wait for Ready=True (typically 1-2 minutes)

# 5. Verify new certificate
kubectl get certificate purple-parser-tls -n purple-parser
kubectl get secret purple-parser-tls -n purple-parser -o jsonpath='{.data.tls\.crt}' | \
    base64 -d | \
    openssl x509 -noout -dates

# 6. Test HTTPS endpoint
curl -v https://parser.your-domain.com/health 2>&1 | grep "SSL certificate verify ok"

# 7. Verify Ingress using new certificate
kubectl describe ingress purple-parser -n purple-parser | grep "tls"
```

**Troubleshooting**:

```bash
# If certificate issuance fails:

# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager --tail=50

# Check certificate events
kubectl describe certificate purple-parser-tls -n purple-parser | grep Events -A 10

# Check DNS resolution (for Let's Encrypt)
nslookup parser.your-domain.com

# Check ClusterIssuer status
kubectl describe clusterissuer letsencrypt-prod

# Common issues:
# - DNS not resolving → Update DNS records
# - Rate limit exceeded → Use staging issuer temporarily
# - Ingress not ready → Check ingress controller
```

---

## 6. Vulnerability Management

### 6.1 Critical Vulnerability Response

**Trigger**: Critical CVE identified in production
**Duration**: 4 hours (target)
**Owner**: Security Team + DevOps

**Procedure**:

```bash
#!/bin/bash
# Critical Vulnerability Response

# Example: Critical CVE in Python dependency

CVE_ID="CVE-2024-12345"
AFFECTED_PACKAGE="requests"
VULNERABLE_VERSION="2.28.0"
FIXED_VERSION="2.31.0"

echo "🚨 Critical Vulnerability Response"
echo "CVE: $CVE_ID"
echo "Package: $AFFECTED_PACKAGE"
echo "Vulnerable: $VULNERABLE_VERSION"
echo "Fixed: $FIXED_VERSION"

# 1. Verify vulnerability affects us (2 minutes)
echo -e "\n1. Verifying impact..."
if grep -q "$AFFECTED_PACKAGE==$VULNERABLE_VERSION" requirements.lock; then
    echo "⚠️  VULNERABLE VERSION IN USE"
else
    echo "✅ Not affected or already patched"
    exit 0
fi

# 2. Assess risk (5 minutes)
echo -e "\n2. Risk Assessment:"
echo "   - CVSS Score: [CHECK NVD]"
echo "   - Exploitability: [PUBLIC EXPLOIT?]"
echo "   - Our Exposure: [INTERNET-FACING?]"
echo "   - Mitigations: [CONTROLS IN PLACE?]"

# 3. Create hotfix branch (1 minute)
echo -e "\n3. Creating hotfix branch..."
git checkout main
git pull origin main
git checkout -b hotfix/cve-$CVE_ID

# 4. Update dependency (5 minutes)
echo -e "\n4. Updating $AFFECTED_PACKAGE..."

# Update version in requirements.in
sed -i "s/$AFFECTED_PACKAGE==.*/$AFFECTED_PACKAGE==$FIXED_VERSION/" requirements.in

# Regenerate requirements.lock with new hashes
pip-compile --generate-hashes requirements.in > requirements.lock

# Commit changes
git add requirements.in requirements.lock
git commit -m "Security: Fix $CVE_ID - Update $AFFECTED_PACKAGE to $FIXED_VERSION"
git push origin hotfix/cve-$CVE_ID

# 5. Build and test (15 minutes)
echo -e "\n5. Building patched image..."
docker build -f Dockerfile.fips -t purple-parser:cve-$CVE_ID-patched .

# Run vulnerability scan on patched image
trivy image --severity CRITICAL --exit-code 1 purple-parser:cve-$CVE_ID-patched

# Run smoke tests
docker run --rm purple-parser:cve-$CVE_ID-patched python3 -m pytest tests/smoke/ -v

# 6. Create PR and get approval (30 minutes)
echo -e "\n6. Creating PR..."
gh pr create \
    --title "Security: Fix $CVE_ID" \
    --body "**CVE**: $CVE_ID
**Package**: $AFFECTED_PACKAGE
**Fixed Version**: $FIXED_VERSION
**CVSS**: [SCORE]
**Impact**: [DESCRIPTION]

**Testing**:
- [x] Vulnerability scan passed
- [x] Smoke tests passed
- [ ] Security team review

**Urgency**: CRITICAL - Requires expedited review" \
    --label security,critical

# 7. Deploy to production (AFTER APPROVAL) (30 minutes)
echo -e "\n7. Deploying to production..."

# Merge PR
gh pr merge hotfix/cve-$CVE_ID --squash

# Tag release
git tag -a v9.0.1-hotfix.$CVE_ID -m "Security hotfix for $CVE_ID"
git push origin v9.0.1-hotfix.$CVE_ID

# Push to ECR
docker tag purple-parser:cve-$CVE_ID-patched $ECR_REPO:v9.0.1-hotfix.$CVE_ID
docker push $ECR_REPO:v9.0.1-hotfix.$CVE_ID

# Update Kubernetes deployment
kubectl set image deployment/purple-parser \
    purple-parser=$ECR_REPO:v9.0.1-hotfix.$CVE_ID \
    -n purple-parser

# Monitor rollout
kubectl rollout status deployment/purple-parser -n purple-parser --timeout=5m

# 8. Verify patch applied (10 minutes)
echo -e "\n8. Verifying patch..."

# Check running image
kubectl get pods -n purple-parser -o jsonpath='{.items[0].spec.containers[0].image}'

# Run Trivy scan on running pod
POD_NAME=$(kubectl get pods -n purple-parser -o jsonpath='{.items[0].metadata.name}')
trivy k8s --severity CRITICAL pod/$POD_NAME -n purple-parser

# 9. Communication (5 minutes)
echo -e "\n9. Stakeholder communication..."
echo "✅ $CVE_ID patched in production"
echo "   - Package: $AFFECTED_PACKAGE $VULNERABLE_VERSION → $FIXED_VERSION"
echo "   - Deployed: v9.0.1-hotfix.$CVE_ID"
echo "   - Verified: Trivy scan clean"

# 10. Post-incident review (within 24h)
echo -e "\n10. Schedule post-incident review"
echo "    - Document timeline"
echo "    - Review response process"
echo "    - Identify improvements"
```

**SLA Targets**:
- **CRITICAL**: Patch within 24 hours
- **HIGH**: Patch within 7 days
- **MEDIUM**: Patch within 30 days
- **LOW**: Patch in next release cycle

---

## 7. Access Management

### 7.1 Grant User Access to Kubernetes

**Duration**: 10 minutes
**Owner**: DevOps Lead
**Approval Required**: Yes (Security Team Lead)

**Procedure**:

```bash
#!/bin/bash
# Grant Kubernetes Access

USERNAME="$1"
ROLE="$2"  # developer, viewer, or admin

if [ -z "$USERNAME" ] || [ -z "$ROLE" ]; then
    echo "Usage: $0 <username> <role>"
    exit 1
fi

echo "Granting Kubernetes access:"
echo "  User: $USERNAME"
echo "  Role: $ROLE"

# 1. Create service account
kubectl create serviceaccount $USERNAME -n purple-parser

# 2. Assign appropriate role
case $ROLE in
    "developer")
        kubectl create rolebinding ${USERNAME}-developer \
            --clusterrole=edit \
            --serviceaccount=purple-parser:$USERNAME \
            -n purple-parser
        ;;
    "viewer")
        kubectl create rolebinding ${USERNAME}-viewer \
            --clusterrole=view \
            --serviceaccount=purple-parser:$USERNAME \
            -n purple-parser
        ;;
    "admin")
        kubectl create rolebinding ${USERNAME}-admin \
            --clusterrole=admin \
            --serviceaccount=purple-parser:$USERNAME \
            -n purple-parser
        ;;
    *)
        echo "Invalid role: $ROLE"
        exit 1
        ;;
esac

# 3. Generate kubeconfig for user
kubectl create token $USERNAME -n purple-parser --duration=8760h > ${USERNAME}-token.txt

echo "✅ Access granted"
echo "   Send ${USERNAME}-token.txt securely to user"
echo "   Token expires in 1 year"
```

**Access Levels**:

| Role | Permissions | Use Case |
|------|-------------|----------|
| **viewer** | Read-only (pods, logs, configs) | Operations team, auditors |
| **developer** | Create/update workloads, no RBAC changes | Development team |
| **admin** | Full namespace control, no cluster-wide | DevOps team leads |

---

### 7.2 Revoke User Access

**Duration**: 5 minutes
**Owner**: DevOps Lead
**Trigger**: User departure, role change, security incident

**Procedure**:

```bash
#!/bin/bash
# Revoke Kubernetes Access

USERNAME="$1"

if [ -z "$USERNAME" ]; then
    echo "Usage: $0 <username>"
    exit 1
fi

echo "Revoking access for: $USERNAME"

# 1. Delete rolebindings
kubectl delete rolebinding -n purple-parser -l user=$USERNAME

# 2. Delete service account
kubectl delete serviceaccount $USERNAME -n purple-parser

# 3. Verify deletion
if kubectl get serviceaccount $USERNAME -n purple-parser 2>/dev/null; then
    echo "❌ Failed to revoke access"
    exit 1
else
    echo "✅ Access revoked successfully"
fi

# 4. Audit log entry
echo "$(date --iso-8601) - Access revoked: $USERNAME by $(whoami)" >> /var/log/access-revocations.log

# 5. Notify security team
echo "⚠️  Notify security team: $USERNAME access revoked"
```

---

## 8. Backup & Recovery

### 8.1 Configuration Backup

**Frequency**: Daily (automated)
**Duration**: 10 minutes
**Owner**: DevOps Automation

**Procedure**:

```bash
#!/bin/bash
# Daily Configuration Backup

BACKUP_DATE=$(date +%Y%m%d)
BACKUP_DIR="./backups/$BACKUP_DATE"
S3_BUCKET="s3://purple-parser-backups"

mkdir -p $BACKUP_DIR

echo "📦 Daily Configuration Backup - $BACKUP_DATE"

# 1. Kubernetes manifests
echo "1. Backing up Kubernetes resources..."
kubectl get all -n purple-parser -o yaml > $BACKUP_DIR/k8s-resources.yaml
kubectl get configmap -n purple-parser -o yaml > $BACKUP_DIR/k8s-configmaps.yaml
kubectl get secret -n purple-parser -o yaml > $BACKUP_DIR/k8s-secrets.yaml

# 2. Application configuration
echo "2. Backing up application config..."
kubectl exec deployment/purple-parser -n purple-parser -- \
    cat /app/config.yaml > $BACKUP_DIR/app-config.yaml

# 3. AIDE baseline
echo "3. Backing up AIDE baseline..."
kubectl exec deployment/purple-parser -n purple-parser -- \
    cat /var/lib/aide/aide.db > $BACKUP_DIR/aide-baseline.db || true

# 4. Security policies
echo "4. Backing up security policies..."
cp security/seccomp-purple-parser.json $BACKUP_DIR/
cp security/apparmor-purple-parser $BACKUP_DIR/
cp security/aide.conf $BACKUP_DIR/

# 5. Upload to S3
echo "5. Uploading to S3..."
aws s3 sync $BACKUP_DIR $S3_BUCKET/$BACKUP_DATE/ \
    --sse AES256 \
    --storage-class STANDARD_IA

# 6. Verify backup
aws s3 ls $S3_BUCKET/$BACKUP_DATE/

echo "✅ Backup complete: $S3_BUCKET/$BACKUP_DATE/"

# 7. Cleanup old local backups (>7 days)
find ./backups/ -type d -mtime +7 -exec rm -rf {} +

# 8. Cleanup old S3 backups (>90 days)
aws s3 ls $S3_BUCKET/ | awk '{print $2}' | while read dir; do
    AGE=$(( ($(date +%s) - $(date -d "${dir%/}" +%s)) / 86400 ))
    if [ $AGE -gt 90 ]; then
        aws s3 rm $S3_BUCKET/$dir --recursive
    fi
done
```

---

### 8.2 Disaster Recovery - Full Restore

**Trigger**: Complete cluster failure or data loss
**Duration**: 2-4 hours
**Owner**: DevOps Lead + Security Team

**Procedure**:

```bash
#!/bin/bash
# Disaster Recovery - Full Restore

RESTORE_DATE="${1:-latest}"
S3_BUCKET="s3://purple-parser-backups"

if [ "$RESTORE_DATE" = "latest" ]; then
    RESTORE_DATE=$(aws s3 ls $S3_BUCKET/ | tail -1 | awk '{print $2}' | tr -d '/')
fi

echo "🚨 DISASTER RECOVERY - Full Restore"
echo "Restore Date: $RESTORE_DATE"
echo "=============================================="

# 1. Download backups
echo "1. Downloading backups from S3..."
mkdir -p ./restore
aws s3 sync $S3_BUCKET/$RESTORE_DATE/ ./restore/

# 2. Restore infrastructure (Terraform)
echo "2. Restoring infrastructure..."
cd terraform/
terraform init
terraform plan
terraform apply -auto-approve
cd ..

# 3. Restore Kubernetes resources
echo "3. Restoring Kubernetes resources..."

# Create namespace
kubectl create namespace purple-parser

# Apply resources
kubectl apply -f ./restore/k8s-resources.yaml
kubectl apply -f ./restore/k8s-configmaps.yaml

# Secrets (manual due to encryption)
echo "⚠️  MANUAL: Restore secrets from AWS Secrets Manager"

# 4. Restore application configuration
echo "4. Restoring application configuration..."
kubectl create configmap app-config \
    --from-file=config.yaml=./restore/app-config.yaml \
    -n purple-parser

# 5. Deploy application
echo "5. Deploying application..."
kubectl apply -f deployment/k8s/deployment.yaml
kubectl apply -f deployment/k8s/service.yaml
kubectl apply -f deployment/k8s/ingress.yaml

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=purple-parser -n purple-parser --timeout=5m

# 6. Restore security policies
echo "6. Restoring security policies..."

# Seccomp profile (to nodes)
for node in $(kubectl get nodes -o name); do
    kubectl debug $node -it --image=alpine -- sh -c "
        mkdir -p /host/var/lib/kubelet/seccomp/
        cat > /host/var/lib/kubelet/seccomp/purple-parser.json <<'EOF'
$(cat ./restore/seccomp-purple-parser.json)
EOF
    "
done

# AppArmor profile (to nodes)
for node in $(kubectl get nodes -o name); do
    kubectl debug $node -it --image=alpine -- sh -c "
        cat > /host/etc/apparmor.d/purple-parser <<'EOF'
$(cat ./restore/apparmor-purple-parser)
EOF
        apparmor_parser -r /host/etc/apparmor.d/purple-parser
    "
done

# 7. Restore AIDE baseline
echo "7. Restoring AIDE baseline..."
kubectl cp ./restore/aide-baseline.db purple-parser-0:/var/lib/aide/aide.db -n purple-parser

# 8. Verify restoration
echo "8. Verifying restoration..."

# Check pod status
kubectl get pods -n purple-parser

# Check application health
sleep 30
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" https://parser.your-domain.com/health)
if [ "$HEALTH" = "200" ]; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed (HTTP $HEALTH)"
fi

# Check logs for errors
kubectl logs deployment/purple-parser -n purple-parser --tail=50

# 9. Post-restoration tasks
echo "9. Post-restoration tasks..."
echo "   - [ ] Verify DNS resolution"
echo "   - [ ] Verify TLS certificates"
echo "   - [ ] Verify API endpoints"
echo "   - [ ] Verify CloudWatch logging"
echo "   - [ ] Verify external-monitoring/alerting"
echo "   - [ ] Test end-to-end workflow"
echo "   - [ ] Notify stakeholders"

echo "✅ Disaster recovery complete"
echo "   Restored from: $RESTORE_DATE"
echo "   RTO: $(date)"
```

**Recovery Objectives**:
- **RTO** (Recovery Time Objective): 4 hours
- **RPO** (Recovery Point Objective): 24 hours (daily backups)

---

## 9. Compliance Operations

### 9.1 Monthly Compliance Report

**Frequency**: First Monday of each month
**Duration**: 2 hours
**Owner**: Compliance Officer + Security Team

**Procedure**:

```bash
#!/bin/bash
# Monthly Compliance Report Generation

REPORT_MONTH=$(date +%Y-%m)
REPORT_FILE="compliance-report-$REPORT_MONTH.md"

echo "# Monthly Compliance Report - Purple Pipeline Parser" > $REPORT_FILE
echo "**Report Period**: $REPORT_MONTH" >> $REPORT_FILE
echo "**Generated**: $(date)" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# 1. STIG Compliance Status
echo "## 1. STIG Compliance" >> $REPORT_FILE
echo "" >> $REPORT_FILE
# Run STIG scanner (manual or automated)
echo "**Overall Compliance**: 76% (35/46 controls)" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# 2. FIPS 140-2 Status
echo "## 2. FIPS 140-2 Compliance" >> $REPORT_FILE
kubectl exec deployment/purple-parser -n purple-parser -- /app/scripts/verify-fips.sh > fips-check.txt
if grep -q "FIPS 140-2 COMPLIANCE VERIFIED" fips-check.txt; then
    echo "**Status**: ✅ COMPLIANT" >> $REPORT_FILE
else
    echo "**Status**: ❌ NON-COMPLIANT" >> $REPORT_FILE
fi
echo "" >> $REPORT_FILE

# 3. Vulnerability Status
echo "## 3. Vulnerability Management" >> $REPORT_FILE
CRITICAL_VULNS=$(kubectl logs job/trivy-scan-latest -n purple-parser | grep "Total: " | awk '{print $2}')
echo "**Critical Vulnerabilities**: $CRITICAL_VULNS" >> $REPORT_FILE
echo "**High Vulnerabilities**: [CHECK MANUALLY]" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# 4. Security Incidents
echo "## 4. Security Incidents" >> $REPORT_FILE
INCIDENT_COUNT=$(aws logs filter-log-events \
    --log-group-name /aws/eks/purple-parser \
    --start-time $(date -d '1 month ago' +%s)000 \
    --filter-pattern "CRITICAL" \
    --query 'events' --output text | wc -l)
echo "**Incidents Reported**: $INCIDENT_COUNT" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# 5. Access Reviews
echo "## 5. Access Reviews" >> $REPORT_FILE
USER_COUNT=$(kubectl get serviceaccounts -n purple-parser --no-headers | wc -l)
echo "**Active Service Accounts**: $USER_COUNT" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# 6. Certificate Status
echo "## 6. Certificate Management" >> $REPORT_FILE
CERT_EXPIRY=$(kubectl get certificate purple-parser-tls -n purple-parser -o jsonpath='{.status.notAfter}')
echo "**TLS Certificate Expires**: $CERT_EXPIRY" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# 7. Secret Rotation
echo "## 7. Secret Rotation Status" >> $REPORT_FILE
LAST_ROTATION=$(aws secretsmanager describe-secret \
    --secret-id purple-parser/prod/anthropic-api-key \
    --query 'LastRotatedDate' --output text)
echo "**Last API Key Rotation**: $LAST_ROTATION" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# 8. Recommendations
echo "## 8. Recommendations" >> $REPORT_FILE
echo "- [List any compliance gaps]" >> $REPORT_FILE
echo "- [List improvement opportunities]" >> $REPORT_FILE
echo "" >> $REPORT_FILE

echo "✅ Compliance report generated: $REPORT_FILE"

# Upload to S3
aws s3 cp $REPORT_FILE s3://purple-parser-compliance-reports/

# Email to stakeholders
# (Configure SES or use external email service)
```

---

## Appendix A: Quick Reference

### Common Commands

```bash
# Check pod status
kubectl get pods -n purple-parser

# View logs
kubectl logs -f deployment/purple-parser -n purple-parser

# Restart deployment
kubectl rollout restart deployment/purple-parser -n purple-parser

# Check CloudWatch alarms
aws cloudwatch describe-alarms --state-value ALARM

# Rotate secret
aws secretsmanager rotate-secret --secret-id purple-parser/prod/anthropic-api-key

# Run Trivy scan
trivy image purple-parser:latest --severity HIGH,CRITICAL

# Check AIDE integrity
kubectl exec deployment/purple-parser -n purple-parser -- aide --check

# Check certificate expiry
kubectl get certificate -n purple-parser
```

### Emergency Contacts

- **On-Call Engineer**: oncall@company.com / PagerDuty @oncall
- **Security Team**: security@company.com / PagerDuty @security
- **CISO**: ciso@company.com / +1-XXX-XXX-XXXX

### Important URLs

- AWS Console: https://console.aws.amazon.com
- GitHub: https://github.com/company/purple-parser
- Status Page: https://status.your-domain.com
- Documentation: https://docs.your-domain.com/purple-parser

---

**Document Maintenance**

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-10-10 | Initial runbooks created | Security Team |

---

**End of Security Runbooks**
