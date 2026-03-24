# Security Incident Response Plan (SIRP)
## Purple Pipeline Parser Eater v9.0.0

**Document Classification**: Internal Use Only
**Last Updated**: 2025-10-10
**Version**: 1.0
**Distribution**: Security Team, On-Call Engineers, Management

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Incident Response Team](#2-incident-response-team)
3. [Incident Classification](#3-incident-classification)
4. [Response Procedures](#4-response-procedures)
5. [Incident Scenarios & Playbooks](#5-incident-scenarios--playbooks)
6. [Communication Plan](#6-communication-plan)
7. [Post-Incident Activities](#7-post-incident-activities)
8. [Tools & Resources](#8-tools--resources)

---

## 1. Executive Summary

### 1.1 Purpose

This Security Incident Response Plan (SIRP) provides procedures for identifying, responding to, and recovering from security incidents affecting Purple Pipeline Parser Eater v9.0.0.

### 1.2 Scope

**In Scope**:
- Security incidents affecting application availability
- Data breaches or unauthorized access
- API key compromise
- Container compromise
- Malicious code detection
- DDoS attacks
- Insider threats

**Out of Scope**:
- AWS infrastructure incidents (handled by AWS Support)
- Third-party service outages (Anthropic, SentinelOne, Observo.ai)
- Non-security operational issues

### 1.3 Goals

1. **Rapid Detection**: Identify security incidents within 15 minutes
2. **Quick Containment**: Contain P0 incidents within 1 hour
3. **Minimize Impact**: Reduce data loss and service disruption
4. **Preserve Evidence**: Maintain forensic integrity for investigation
5. **Learn & Improve**: Conduct post-incident reviews and improve defenses

### 1.4 Service Level Objectives (SLOs)

| Incident Priority | Detection Time | Initial Response | Containment | Resolution |
|-------------------|----------------|------------------|-------------|------------|
| **P0 - Critical** | 5 minutes | 15 minutes | 1 hour | 4 hours |
| **P1 - High** | 15 minutes | 1 hour | 4 hours | 24 hours |
| **P2 - Medium** | 1 hour | 4 hours | 24 hours | 7 days |
| **P3 - Low** | 4 hours | 24 hours | 7 days | 30 days |

---

## 2. Incident Response Team

### 2.1 Team Structure

```
┌─────────────────────────────────────────────────────────────────┐
│              INCIDENT RESPONSE TEAM STRUCTURE                    │
└─────────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │  Incident        │
                    │  Commander       │
                    │  (IC)            │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
  ┌─────▼─────┐      ┌───────▼──────┐     ┌──────▼──────┐
  │ Technical │      │ Communications│     │  Legal &    │
  │   Lead    │      │     Lead      │     │ Compliance  │
  └─────┬─────┘      └───────┬──────┘     └──────┬──────┘
        │                    │                    │
  ┌─────┴─────┐      ┌───────┴──────┐     ┌──────┴──────┐
  │• Security │      │• PR Team     │     │• Legal      │
  │• DevOps   │      │• Customer    │     │• Compliance │
  │• Dev Team │      │  Support     │     │• Privacy    │
  └───────────┘      └──────────────┘     └─────────────┘
```

### 2.2 Roles & Responsibilities

#### Incident Commander (IC)
**Primary**: Security Team Lead
**Backup**: CISO

**Responsibilities**:
- Overall incident coordination
- Declare incident severity
- Authorize major actions (e.g., service shutdown)
- Communication with executive leadership
- Declare incident resolved
- Initiate post-incident review

**Authority**:
- Can override normal change control processes
- Can allocate resources as needed
- Can engage external assistance (forensics, legal)

#### Technical Lead
**Primary**: Senior Security Engineer
**Backup**: DevOps Lead

**Responsibilities**:
- Technical investigation and analysis
- Containment strategy development
- Evidence collection and preservation
- Eradication of threats
- System restoration
- Technical documentation

#### Communications Lead
**Primary**: Director of Communications
**Backup**: Customer Success Manager

**Responsibilities**:
- Internal communications (employees, leadership)
- External communications (customers, public)
- Status page updates
- Media relations
- Regulatory notifications (if required)

#### Legal & Compliance Lead
**Primary**: General Counsel
**Backup**: Compliance Officer

**Responsibilities**:
- Legal advice during incident
- Regulatory compliance (GDPR, HIPAA, etc.)
- Law enforcement coordination
- Breach notification requirements
- Contractual obligations review

### 2.3 Contact Information

| Role | Name | Email | Phone | PagerDuty |
|------|------|-------|-------|-----------|
| **Incident Commander** | [Name] | ic@company.com | +1-XXX-XXX-XXXX | @ic-team |
| **Technical Lead** | [Name] | security@company.com | +1-XXX-XXX-XXXX | @security |
| **Communications Lead** | [Name] | comms@company.com | +1-XXX-XXX-XXXX | @comms |
| **Legal Lead** | [Name] | legal@company.com | +1-XXX-XXX-XXXX | @legal |
| **On-Call Engineer** | [Rotation] | oncall@company.com | +1-XXX-XXX-XXXX | @oncall |

### 2.4 Escalation Path

```
Level 1: On-Call Engineer
   │
   │ (P0/P1 incidents or unable to resolve in 30 min)
   ▼
Level 2: Security Team Lead
   │
   │ (P0 incidents or customer-impacting)
   ▼
Level 3: CISO
   │
   │ (Data breach or major service outage)
   ▼
Level 4: CEO / Board of Directors
```

---

## 3. Incident Classification

### 3.1 Severity Levels

#### P0 - Critical
**Definition**: Confirmed security breach with immediate business impact

**Examples**:
- Active data breach in progress
- API keys compromised and being used maliciously
- Complete service outage due to security incident
- Ransomware infection
- Unauthorized access to production systems

**Response SLA**:
- Detection: 5 minutes
- Initial Response: 15 minutes
- Containment: 1 hour
- Resolution: 4 hours

**Escalation**: Immediate notification to CISO and CEO

#### P1 - High
**Definition**: Significant security incident with potential business impact

**Examples**:
- Failed authentication attempts (brute force)
- Container compromise (contained)
- Suspicious network activity
- Vulnerability exploitation attempt
- Insider threat investigation

**Response SLA**:
- Detection: 15 minutes
- Initial Response: 1 hour
- Containment: 4 hours
- Resolution: 24 hours

**Escalation**: Notification to Security Team Lead

#### P2 - Medium
**Definition**: Security event requiring investigation but no immediate impact

**Examples**:
- AIDE file integrity alerts
- Repeated CSRF validation failures
- Anomalous API usage patterns
- Security policy violations
- Non-critical vulnerability exploitation

**Response SLA**:
- Detection: 1 hour
- Initial Response: 4 hours
- Containment: 24 hours
- Resolution: 7 days

**Escalation**: On-Call Engineer handles, escalate if needed

#### P3 - Low
**Definition**: Minor security event or informational alert

**Examples**:
- Single failed authentication
- Expected security scans (Trivy findings)
- Certificate expiration warnings (>30 days)
- Low-severity vulnerability findings
- Security awareness training gaps

**Response SLA**:
- Detection: 4 hours
- Initial Response: 24 hours
- Containment: 7 days
- Resolution: 30 days

**Escalation**: Tracked in ticketing system, no immediate escalation

### 3.2 Incident Categories

| Category | Description | Example Indicators |
|----------|-------------|-------------------|
| **Unauthorized Access** | Successful breach of authentication/authorization | Failed auth → success, unusual API calls |
| **Data Breach** | Confirmed exfiltration of confidential data | Large data transfers, API key usage from unknown IPs |
| **Malware/Ransomware** | Malicious software detected or executed | File encryption, suspicious processes |
| **Denial of Service** | Service unavailable due to attack | Excessive requests, resource exhaustion |
| **Code Injection** | Malicious code execution (Lua, container) | os.execute in logs, unexpected syscalls |
| **Insider Threat** | Malicious actions by authorized user | Off-hours access, privilege escalation |
| **Supply Chain** | Compromised dependency or infrastructure | Malicious package, backdoored image |
| **Compliance Violation** | Security policy or regulation violation | Unencrypted data, improper logging |

---

## 4. Response Procedures

### 4.1 Incident Response Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                  INCIDENT RESPONSE LIFECYCLE                     │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │  1. DETECT   │
    │  Identify    │
    │  incident    │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  2. TRIAGE   │
    │  Classify &  │
    │  prioritize  │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  3. CONTAIN  │
    │  Limit       │
    │  damage      │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │ 4. INVESTIGATE│
    │  Root cause  │
    │  analysis    │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │ 5. ERADICATE │
    │  Remove      │
    │  threat      │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  6. RECOVER  │
    │  Restore     │
    │  services    │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │7. POST-MORTEM│
    │  Learn &     │
    │  improve     │
    └──────────────┘
```

### 4.2 Phase 1: Detection

**Objective**: Identify potential security incidents

**Detection Sources**:
1. **Automated Alerts**
   - CloudWatch Alarms (authentication failures, errors)
   - AIDE file integrity violations
   - Trivy critical vulnerability findings
   - Kubernetes events (pod crashes, OOMKills)

2. **Manual Detection**
   - User reports
   - Security team monitoring
   - Log analysis (CloudWatch Insights)
   - External notifications (vendor, researcher)

3. **Threat Intelligence**
   - AWS GuardDuty findings
   - Third-party threat feeds
   - Security advisories (NIST, CISA)

**Actions**:
1. Document detection source and timestamp
2. Capture initial indicators (IP addresses, usernames, error messages)
3. Create incident ticket in tracking system
4. Proceed to Triage phase

### 4.3 Phase 2: Triage

**Objective**: Assess severity and mobilize appropriate response

**Triage Questions**:
1. Is this a confirmed incident or false positive?
2. What assets are affected?
3. Is confidential data involved?
4. Is the incident ongoing or past event?
5. What is the business impact?
6. What is the incident category?

**Triage Checklist**:
- [ ] Confirm incident is real (not false positive)
- [ ] Assign severity level (P0-P3)
- [ ] Assign incident category
- [ ] Identify affected systems and data
- [ ] Assess business impact
- [ ] Page appropriate team members
- [ ] Declare incident in Slack/Teams
- [ ] Create Zoom/Teams incident bridge
- [ ] Assign Incident Commander

**Decision**: Proceed to Containment or close as false positive

### 4.4 Phase 3: Containment

**Objective**: Limit damage and prevent spread

**Short-Term Containment** (minutes to hours):
```bash
# Isolate compromised pod
kubectl cordon <node-name>
kubectl delete pod <pod-name> -n purple-parser

# Block malicious IP at WAF
aws wafv2 update-ip-set --id <ip-set-id> \
    --addresses <malicious-ip>/32

# Rotate compromised API key
aws secretsmanager rotate-secret \
    --secret-id purple-parser/prod/anthropic-api-key

# Disable user account (if insider threat)
aws iam attach-user-policy --user-name <user> \
    --policy-arn arn:aws:iam::aws:policy/AWSDenyAll
```

**Long-Term Containment** (hours to days):
- Deploy patched version
- Update security policies
- Implement additional monitoring
- Enhance network segmentation

**Evidence Preservation**:
```bash
# Snapshot EBS volumes
aws ec2 create-snapshot --volume-id <vol-id> \
    --description "Forensic snapshot - Incident #123"

# Export CloudWatch Logs
aws logs create-export-task \
    --log-group-name /aws/eks/purple-parser \
    --from $(date -d '2 hours ago' +%s)000 \
    --to $(date +%s)000 \
    --destination s3://forensics-bucket/incident-123/

# Capture memory dump (if needed)
kubectl exec <pod-name> -- gcore 1 > incident-123-memory.dump

# Preserve container image
docker save purple-parser:suspect > incident-123-image.tar
```

### 4.5 Phase 4: Investigation

**Objective**: Determine root cause and scope

**Investigation Steps**:

1. **Timeline Construction**
   - When did the incident start?
   - When was it first detected?
   - What actions occurred?
   - When did the incident end (if contained)?

2. **Scope Determination**
   - How many systems affected?
   - How many users affected?
   - What data was accessed/exfiltrated?
   - Are there other related incidents?

3. **Root Cause Analysis**
   - What vulnerability was exploited?
   - How did the attacker gain access?
   - What was the attack vector?
   - What tools/techniques were used?

**Investigation Tools**:
```bash
# CloudWatch Insights - Authentication failures
aws logs start-query \
    --log-group-name /aws/eks/purple-parser \
    --start-time $(date -d '24 hours ago' +%s) \
    --end-time $(date +%s) \
    --query-string 'fields @timestamp, level, message
    | filter level = "ERROR" and message like /authentication/
    | sort @timestamp desc'

# Kubernetes events
kubectl get events -n purple-parser --sort-by='.lastTimestamp'

# CloudTrail - IAM activity
aws cloudtrail lookup-events \
    --lookup-attributes AttributeKey=Username,AttributeValue=<user> \
    --start-time $(date -d '24 hours ago' --iso-8601) \
    --max-results 100

# Network connections (if pod still running)
kubectl exec <pod-name> -n purple-parser -- netstat -tupn
```

**Documentation**:
- Maintain detailed timeline in incident ticket
- Screenshot all evidence
- Log all commands executed
- Document all findings

### 4.6 Phase 5: Eradication

**Objective**: Remove threat from environment

**Eradication Actions**:

**For Malware/Backdoor**:
```bash
# Delete compromised pods
kubectl delete pod <pod-name> -n purple-parser --force

# Rebuild and redeploy from clean base
docker build -f Dockerfile.fips -t purple-parser:clean .
kubectl set image deployment/purple-parser \
    purple-parser=purple-parser:clean -n purple-parser
```

**For Compromised Credentials**:
```bash
# Rotate all API keys
for secret in anthropic-api-key s1-credentials observo-credentials; do
    aws secretsmanager rotate-secret \
        --secret-id purple-parser/prod/$secret
done

# Rotate TLS certificates
kubectl delete certificate purple-parser-tls -n purple-parser
kubectl apply -f deployment/k8s/certificate.yaml
```

**For Vulnerabilities**:
```bash
# Apply security patches
pip install --upgrade <vulnerable-package>==<fixed-version>
docker build -f Dockerfile.fips -t purple-parser:patched .

# Update requirements.lock with new hashes
pip-compile --generate-hashes requirements.in > requirements.lock
```

**For Insider Threat**:
- Revoke all access (AWS IAM, Kubernetes RBAC, GitHub)
- Reset all passwords
- Review all actions taken by user (CloudTrail)
- Coordinate with HR and Legal

**Verification**:
- Run vulnerability scans (Trivy, pip-audit)
- Verify AIDE baseline
- Check file integrity
- Validate all patches applied

### 4.7 Phase 6: Recovery

**Objective**: Restore systems to normal operation

**Recovery Steps**:

1. **Validation**
   - Verify threat is eradicated
   - Confirm systems are clean
   - Test functionality
   - Run smoke tests

2. **Restore Services**
```bash
# Scale up deployment
kubectl scale deployment purple-parser --replicas=3 -n purple-parser

# Remove node cordons
kubectl uncordon <node-name>

# Verify health
kubectl get pods -n purple-parser
kubectl logs -f <pod-name> -n purple-parser
curl https://parser.your-domain.com/health
```

3. **Monitor Closely**
   - Increase monitoring frequency (15-minute checks)
   - Set up additional alerts
   - Watch for reinfection
   - Monitor for 72 hours post-recovery

4. **Communication**
   - Notify stakeholders of recovery
   - Update status page
   - Send all-clear notification

**Recovery Checklist**:
- [ ] All threats eradicated (verified)
- [ ] All patches applied
- [ ] All credentials rotated
- [ ] Services restored to normal operation
- [ ] Monitoring enhanced
- [ ] 72-hour watch period initiated
- [ ] Stakeholders notified
- [ ] Incident ticket updated

### 4.8 Phase 7: Post-Incident Review

**Objective**: Learn from incident and improve defenses

**Post-Incident Review Meeting** (within 5 business days):
- **Attendees**: Incident Response Team, relevant stakeholders
- **Duration**: 60-90 minutes
- **Format**: Blameless post-mortem

**Agenda**:
1. Incident timeline review (10 minutes)
2. What went well? (15 minutes)
3. What went wrong? (20 minutes)
4. Where were we lucky? (10 minutes)
5. Action items (20 minutes)
6. Documentation review (10 minutes)

**Deliverables**:
- Post-incident report (written)
- Action items with owners and due dates
- Updated runbooks (if needed)
- Threat model updates
- Training materials (if needed)

**Post-Incident Report Template**:
```markdown
# Post-Incident Report: [Incident Title]

**Incident ID**: INC-2025-001
**Date**: 2025-10-10
**Severity**: P1 - High
**Duration**: 3 hours 45 minutes
**Incident Commander**: [Name]

## Executive Summary
[2-3 paragraph summary for leadership]

## Timeline
| Time (UTC) | Event |
|------------|-------|
| 14:00 | Alert triggered: Authentication failures |
| 14:15 | On-call engineer investigating |
| 14:30 | Incident declared (P1) |
| ...   | ... |
| 17:45 | Incident resolved |

## Root Cause
[Detailed technical explanation]

## Impact
- **Users Affected**: 0
- **Data Compromised**: None
- **Downtime**: 0 minutes
- **Financial Impact**: $XXX (API usage)

## What Went Well
- Detection within 5 minutes
- Rapid escalation
- Effective containment

## What Went Wrong
- Initial containment strategy incomplete
- Documentation gaps in runbook
- Communication delay to stakeholders

## Action Items
| # | Action | Owner | Due Date | Priority |
|---|--------|-------|----------|----------|
| 1 | Update runbook section 4.3 | Security | 2025-10-15 | High |
| 2 | Implement additional monitoring | DevOps | 2025-10-20 | Medium |
| 3 | Conduct tabletop exercise | Security | 2025-11-01 | Low |

## Lessons Learned
[Key takeaways for future incidents]
```

---

## 5. Incident Scenarios & Playbooks

### 5.1 Scenario 1: API Key Compromise

**Indicators**:
- API usage from unknown IP addresses
- Unusual API call patterns (high volume)
- API errors from unexpected sources
- CloudTrail shows unauthorized secret access

**Playbook**:

```bash
# 1. IMMEDIATE CONTAINMENT (5 minutes)

# Invalidate current API key immediately
aws secretsmanager put-secret-value \
    --secret-id purple-parser/prod/anthropic-api-key \
    --secret-string '{"api_key":"REVOKED"}'

# Restart all pods to pick up revoked key (prevents further usage)
kubectl rollout restart deployment/purple-parser -n purple-parser

# 2. INVESTIGATE SOURCE (15 minutes)

# Check CloudTrail for secret access
aws cloudtrail lookup-events \
    --lookup-attributes AttributeKey=ResourceName,\
AttributeValue=purple-parser/prod/anthropic-api-key \
    --start-time $(date -d '7 days ago' --iso-8601) \
    --max-results 100

# Check application logs for unusual API calls
aws logs start-query \
    --log-group-name /aws/eks/purple-parser \
    --query-string 'fields @timestamp, request_id, message
    | filter message like /anthropic_api/
    | stats count() by bin(5m)'

# Check Anthropic API usage (if available)
# Contact Anthropic support to review recent API usage

# 3. GENERATE NEW KEY (30 minutes)

# Generate new Anthropic API key via Anthropic console
# Update secret in AWS Secrets Manager
aws secretsmanager update-secret \
    --secret-id purple-parser/prod/anthropic-api-key \
    --secret-string '{"api_key":"sk-ant-api03-NEW_KEY_HERE"}'

# Trigger pod restart to pick up new key
kubectl rollout restart deployment/purple-parser -n purple-parser

# Verify new key works
kubectl logs -f deployment/purple-parser -n purple-parser | grep anthropic

# 4. ROOT CAUSE ANALYSIS (1 hour)

# Determine how key was compromised:
# - Check CloudWatch Logs for key in logs (should be redacted)
# - Check GitHub for hardcoded keys (should be prevented)
# - Check developer workstations (if insider threat)
# - Check for container compromise (memory dump)

# 5. NOTIFY STAKEHOLDERS (immediate)

# Notify Anthropic of compromise
# Notify management of incident
# Update status page if customer-impacting

# 6. POST-INCIDENT ACTIONS (within 7 days)

# - Rotate all other API keys (SentinelOne, Observo.ai)
# - Review IAM policies for overly permissive access
# - Enhance monitoring for secret access
# - Conduct training on secret management
# - Update incident response runbook with lessons learned
```

**Recovery Verification**:
- [ ] Old API key confirmed revoked
- [ ] New API key functioning correctly
- [ ] No API errors in logs
- [ ] Application processing requests normally
- [ ] CloudTrail shows only authorized access
- [ ] Anthropic confirms no suspicious activity

---

### 5.2 Scenario 2: Container Compromise

**Indicators**:
- Unexpected processes in container
- Network connections to unknown IPs
- AIDE file integrity alerts
- Unusual syscall patterns (seccomp logs)
- Increased resource usage (CPU, memory)

**Playbook**:

```bash
# 1. IMMEDIATE CONTAINMENT (5 minutes)

# Identify compromised pod
kubectl get pods -n purple-parser -o wide

# Isolate pod from network (network policy)
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: isolate-compromised-pod
  namespace: purple-parser
spec:
  podSelector:
    matchLabels:
      app: purple-parser
      pod-name: purple-parser-abc123
  policyTypes:
  - Ingress
  - Egress
  # No ingress or egress rules = deny all
EOF

# Mark node as unschedulable to prevent other pods
kubectl cordon <node-name>

# 2. EVIDENCE COLLECTION (15 minutes)

# Capture process list
kubectl exec <pod-name> -n purple-parser -- ps auxf > incident-processes.txt

# Capture network connections
kubectl exec <pod-name> -n purple-parser -- netstat -tupn > incident-network.txt

# Capture file changes (AIDE)
kubectl exec <pod-name> -n purple-parser -- aide --check > incident-aide.txt

# Capture pod logs
kubectl logs <pod-name> -n purple-parser --all-containers > incident-logs.txt

# Capture pod description
kubectl describe pod <pod-name> -n purple-parser > incident-pod-desc.txt

# Optional: Memory dump (requires forensics tools)
# kubectl exec <pod-name> -n purple-parser -- gcore 1 > incident-memory.dump

# 3. TERMINATE COMPROMISED POD (immediate after evidence collection)

kubectl delete pod <pod-name> -n purple-parser --force --grace-period=0

# 4. INVESTIGATE ROOT CAUSE (1 hour)

# Check for container escape indicators
kubectl logs <pod-name> -n purple-parser | grep -i "segfault\|kernel\|panic"

# Check Kubernetes events
kubectl get events -n purple-parser --sort-by='.lastTimestamp' | grep <pod-name>

# Check seccomp/AppArmor violations
sudo dmesg | grep -i "apparmor\|seccomp" | grep purple-parser

# Review recent deployments
kubectl rollout history deployment/purple-parser -n purple-parser

# Check container image for vulnerabilities
trivy image --severity HIGH,CRITICAL purple-parser:current

# 5. ERADICATION (30 minutes)

# If vulnerability in image, rebuild and redeploy
docker build -f Dockerfile.fips -t purple-parser:patched .
trivy image --exit-code 1 --severity CRITICAL purple-parser:patched

# Push to registry
docker push purple-parser:patched

# Update deployment
kubectl set image deployment/purple-parser \
    purple-parser=purple-parser:patched -n purple-parser

# If container escape via kernel vuln, patch host OS
# (Requires node maintenance window)

# 6. RECOVERY (45 minutes)

# Remove isolation network policy
kubectl delete networkpolicy isolate-compromised-pod -n purple-parser

# Uncordon node (after verification clean)
kubectl uncordon <node-name>

# Scale deployment back to normal
kubectl scale deployment purple-parser --replicas=3 -n purple-parser

# Monitor for 72 hours
watch kubectl get pods -n purple-parser
```

**Recovery Verification**:
- [ ] All compromised pods terminated
- [ ] Vulnerability patched (image or host)
- [ ] AIDE baseline regenerated
- [ ] No file integrity violations
- [ ] No unusual network connections
- [ ] All pods running normally
- [ ] Enhanced monitoring active (72 hours)

---

### 5.3 Scenario 3: Malicious Lua Code Deployment

**Indicators**:
- Pipeline validator repeated failures with same pattern
- os.execute() or io.popen() detected in logs
- Observo.ai platform showing unusual activity
- User report of malicious parser

**Playbook**:

```bash
# 1. IMMEDIATE CONTAINMENT (10 minutes)

# Identify malicious parser
export PARSER_ID="suspicious-parser-uuid"

# Quarantine parser file
kubectl exec deployment/purple-parser -n purple-parser -- \
    mv /app/output/${PARSER_ID}.lua /app/quarantine/${PARSER_ID}.lua.quarantine

# Check if deployed to Observo.ai
# (Manual check via Observo.ai console)

# If deployed, remove from Observo.ai immediately
# (API call or manual via Observo console)

# 2. INVESTIGATE SCOPE (30 minutes)

# Find who created the parser
kubectl logs deployment/purple-parser -n purple-parser | grep ${PARSER_ID}

# Check validation logs
aws logs filter-log-events \
    --log-group-name /aws/eks/purple-parser \
    --filter-pattern "${PARSER_ID}" \
    --start-time $(date -d '7 days ago' +%s)000

# Retrieve parser content
kubectl exec deployment/purple-parser -n purple-parser -- \
    cat /app/quarantine/${PARSER_ID}.lua.quarantine

# Check for similar patterns in other parsers
kubectl exec deployment/purple-parser -n purple-parser -- \
    grep -r "os\.execute\|io\.popen" /app/output/ || echo "No matches found"

# 3. DETERMINE INTENT (1 hour)

# Was this:
# - Accidental (user error)?
# - Claude hallucination?
# - Intentional malicious prompt?
# - Insider threat?

# Review Claude API prompts (if logged)
aws logs filter-log-events \
    --log-group-name /aws/eks/purple-parser \
    --filter-pattern "claude_api" \
    --start-time $(date -d '24 hours ago' +%s)000

# Check user account activity
# (Review CloudTrail, application logs)

# 4. ERADICATION (15 minutes)

# Delete quarantined file
kubectl exec deployment/purple-parser -n purple-parser -- \
    rm -f /app/quarantine/${PARSER_ID}.lua.quarantine

# If insider threat, revoke access
# (IAM, Kubernetes RBAC, GitHub)

# If validator bypass, enhance validation rules
# (Update pipeline_validator.py with new patterns)

# 5. PREVENTION ENHANCEMENTS (2 hours)

# Implement Lua sandbox (future enhancement)
# Add AI-based malicious code detection
# Require peer review for high-risk prompts
# Enhanced logging of Claude API responses

# Update validator with new detection pattern
cat >> components/pipeline_validator.py <<'EOF'
# Additional dangerous patterns
DANGEROUS_PATTERNS = [
    r'os\.execute',
    r'io\.popen',
    r'loadstring',
    r'dofile',
    # Add newly discovered pattern
    r'<new_pattern_here>',
]
EOF

# Deploy updated validator
kubectl rollout restart deployment/purple-parser -n purple-parser
```

**Recovery Verification**:
- [ ] Malicious parser deleted
- [ ] Observo.ai platform clean (verified)
- [ ] Validator updated with new patterns
- [ ] User access reviewed/revoked (if needed)
- [ ] No other malicious parsers found
- [ ] Enhanced monitoring active

---

### 5.4 Scenario 4: DDoS Attack

**Indicators**:
- Excessive requests from single or distributed IPs
- ALB health checks failing
- Pods crashing (OOMKilled)
- High CPU/memory usage
- CloudWatch Alarm: API error rate > 50/min

**Playbook**:

```bash
# 1. IMMEDIATE CONTAINMENT (5 minutes)

# Enable AWS Shield Advanced (if not already enabled)
# Update WAF rate limiting rules (aggressive)
aws wafv2 update-rule-group \
    --id <rule-group-id> \
    --scope REGIONAL \
    --lock-token <lock-token> \
    --updates 'Action=INSERT,ActivatedRule={Priority=1,RuleId=<rate-limit-rule>,Action={Block={}}}'

# Adjust rate limits temporarily
# From: 1000 req/5min → 100 req/5min
aws wafv2 update-rule \
    --id <rate-limit-rule-id> \
    --scope REGIONAL \
    --rule-id <rate-limit-rule> \
    --rate-limit 100

# 2. IDENTIFY ATTACK SOURCE (15 minutes)

# Check ALB access logs for top IPs
aws s3 cp s3://alb-logs-bucket/purple-parser/ - --recursive | \
    grep "$(date +%Y/%m/%d)" | \
    awk '{print $3}' | sort | uniq -c | sort -nr | head -20

# Check for specific attack patterns
# - User-Agent patterns
# - Request paths
# - Geographic distribution

# Identify if bot traffic (User-Agent analysis)
aws logs start-query \
    --log-group-name /aws/elasticloadbalancing/purple-parser \
    --query-string 'fields @timestamp, userAgent, clientIp
    | stats count() by userAgent
    | sort count desc'

# 3. BLOCK ATTACK SOURCES (immediate)

# Block malicious IPs at WAF
for ip in <malicious_ip1> <malicious_ip2>; do
    aws wafv2 update-ip-set \
        --id <ip-blocklist-id> \
        --scope REGIONAL \
        --addresses ${ip}/32
done

# Block User-Agent patterns (if bot attack)
aws wafv2 create-regex-pattern-set \
    --name malicious-user-agents \
    --scope REGIONAL \
    --regular-expression-list '{"RegexString":"BadBot|Scraper|.*curl.*"}'

# If geographic attack, enable geo-blocking
aws wafv2 create-rule \
    --name block-country \
    --priority 10 \
    --action Block \
    --statement '{"GeoMatchStatement":{"CountryCodes":["XX","YY"]}}'

# 4. SCALE INFRASTRUCTURE (if needed)

# Increase HPA max replicas temporarily
kubectl patch hpa purple-parser -n purple-parser \
    -p '{"spec":{"maxReplicas":10}}'

# Manually scale up (if HPA insufficient)
kubectl scale deployment purple-parser --replicas=10 -n purple-parser

# Monitor scaling
kubectl get hpa -n purple-parser -w

# 5. MONITOR & ADJUST (ongoing)

# Watch metrics
watch 'kubectl top pods -n purple-parser'
watch 'kubectl get pods -n purple-parser'

# Check if attack mitigated
curl -I https://parser.your-domain.com/health

# Review WAF metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/WAFV2 \
    --metric-name BlockedRequests \
    --dimensions Name=Rule,Value=rate-limit \
    --start-time $(date -d '1 hour ago' --iso-8601) \
    --end-time $(date --iso-8601) \
    --period 300 \
    --statistics Sum

# 6. RECOVERY (after attack subsides)

# Gradually relax rate limits (over 24-48 hours)
# Monitor for attack resumption

# Scale down infrastructure
kubectl scale deployment purple-parser --replicas=3 -n purple-parser
kubectl patch hpa purple-parser -n purple-parser \
    -p '{"spec":{"maxReplicas":5}}'

# Remove temporary IP blocks (if legitimate traffic affected)
# Keep WAF rules in place for 30 days
```

**Recovery Verification**:
- [ ] Attack traffic blocked (>95%)
- [ ] Legitimate traffic flowing normally
- [ ] Pod metrics normal (CPU, memory)
- [ ] ALB health checks passing
- [ ] No error alerts
- [ ] WAF metrics show significant blocked requests
- [ ] Service restored to normal operation

---

## 6. Communication Plan

### 6.1 Internal Communications

**Slack/Teams Channels**:
- `#security-incidents` - Primary incident channel
- `#purple-parser-ops` - Operational updates
- `#leadership` - Executive notifications

**Communication Template**:
```
🚨 SECURITY INCIDENT DECLARED 🚨

**Incident ID**: INC-2025-001
**Severity**: P1 - High
**Status**: INVESTIGATING
**Incident Commander**: @security-lead

**Summary**: [Brief description]

**Impact**:
- Users: None currently
- Services: Purple Parser API response time +20%

**Actions Taken**:
- Isolated compromised pod
- Evidence collection in progress

**Next Update**: In 30 minutes

**Incident Bridge**: [Zoom/Teams link]
```

**Update Frequency**:
- P0: Every 15 minutes
- P1: Every 30 minutes
- P2: Every 4 hours
- P3: Daily

### 6.2 External Communications

**Status Page**: status.your-domain.com

**Update Template**:
```
[INVESTIGATING] Purple Pipeline Parser - Increased API Latency

We are currently investigating reports of increased API latency
affecting the Purple Pipeline Parser service.

Posted: 2025-10-10 14:30 UTC
Next Update: 2025-10-10 15:00 UTC

For urgent inquiries, please contact: support@company.com
```

**Customer Notification** (if data breach):
```
Subject: Important Security Notice - Purple Pipeline Parser

Dear [Customer],

We are writing to inform you of a security incident that may have
affected your data. On [DATE], we discovered [DESCRIPTION].

**What Happened**:
[Brief technical explanation]

**What Information Was Involved**:
[Specific data types]

**What We're Doing**:
[Remediation actions]

**What You Can Do**:
[Recommended customer actions]

We sincerely apologize for any inconvenience this may cause. If you
have any questions, please contact our security team at:
security@company.com

Sincerely,
[Name]
[Title]
```

### 6.3 Regulatory Notifications

**GDPR** (if EU customer data affected):
- Notification to supervisory authority within 72 hours
- Notification to affected individuals "without undue delay"

**HIPAA** (if healthcare data affected):
- Notification to HHS within 60 days
- Notification to affected individuals within 60 days
- Notification to media (if >500 individuals)

**State Laws** (e.g., California CCPA):
- Varies by state, consult legal team

---

## 7. Post-Incident Activities

### 7.1 Incident Closure Checklist

- [ ] All threats eradicated
- [ ] All systems restored
- [ ] 72-hour monitoring period completed
- [ ] Post-incident review conducted
- [ ] Post-incident report published
- [ ] Action items assigned with due dates
- [ ] Stakeholders notified of closure
- [ ] Status page updated (resolved)
- [ ] Incident ticket closed

### 7.2 Metrics & KPIs

Track the following for each incident:

| Metric | Definition | Target |
|--------|------------|--------|
| **MTTD** | Mean Time To Detect | <15 minutes |
| **MTTR** | Mean Time To Respond | P0: <15min, P1: <1hr |
| **MTTC** | Mean Time To Contain | P0: <1hr, P1: <4hr |
| **MTTR** | Mean Time To Recover | P0: <4hr, P1: <24hr |
| **Incident Count** | Total incidents per month | Trend down |
| **False Positive Rate** | % alerts that are false positives | <10% |

### 7.3 Continuous Improvement

**Quarterly Review**:
- Review all incidents from previous quarter
- Identify trends and patterns
- Update threat model
- Update runbooks
- Conduct tabletop exercise

**Annual Review**:
- Full IR plan review and update
- External penetration test
- Red team exercise
- IR team training
- Management briefing

---

## 8. Tools & Resources

### 8.1 Incident Response Tools

| Tool | Purpose | Access |
|------|---------|--------|
| **PagerDuty** | Alerting and escalation | https://company.pagerduty.com |
| **Slack** | Team communication | #security-incidents |
| **Zoom** | Incident bridge | [Dedicated room] |
| **Jira** | Incident tracking | https://company.atlassian.net |
| **AWS Console** | Infrastructure access | https://console.aws.amazon.com |
| **kubectl** | Kubernetes management | CLI tool |
| **CloudWatch** | Logging and monitoring | AWS Console |

### 8.2 External Resources

- **AWS Support**: +1-XXX-XXX-XXXX (Premium Support)
- **Anthropic Support**: support@anthropic.com
- **SentinelOne Support**: support@sentinelone.com
- **Observo.ai Support**: support@observo.ai
- **External Forensics**: [Forensics Firm Contact]
- **Legal Counsel**: [Law Firm Contact]
- **Cyber Insurance**: [Insurance Provider]

### 8.3 Reference Documentation

- [System Security Plan](SYSTEM_SECURITY_PLAN.md)
- [Security Architecture](SECURITY_ARCHITECTURE.md)
- [Threat Model](THREAT_MODEL.md)
- [Data Flow Diagrams](DATA_FLOW_DIAGRAMS.md)
- [Security Runbooks](SECURITY_RUNBOOKS.md)
- [AWS Incident Response Guide](https://aws.amazon.com/premiumsupport/knowledge-center/incident-response/)
- [NIST Incident Response Guide](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r2.pdf)

---

## Appendix A: Incident Response Cheat Sheet

### Quick Reference Commands

```bash
# Check pod status
kubectl get pods -n purple-parser -o wide

# View recent logs
kubectl logs -f deployment/purple-parser -n purple-parser --tail=100

# Check CloudWatch alarms
aws cloudwatch describe-alarms --state-value ALARM

# Rotate API key
aws secretsmanager rotate-secret --secret-id purple-parser/prod/anthropic-api-key

# Isolate pod (network policy)
kubectl apply -f incident-isolate-pod.yaml

# Check AIDE integrity
kubectl exec <pod> -n purple-parser -- aide --check

# Export logs for forensics
aws logs create-export-task --log-group-name /aws/eks/purple-parser \
    --from $(date -d '2 hours ago' +%s)000 --to $(date +%s)000 \
    --destination s3://forensics-bucket/

# Block IP at WAF
aws wafv2 update-ip-set --id <ip-set-id> --addresses <ip>/32

# Scale deployment
kubectl scale deployment purple-parser --replicas=5 -n purple-parser
```

---

**Document Approval**

| Role | Name | Date |
|------|------|------|
| **CISO** | [Name] | 2025-10-10 |
| **Incident Commander** | [Name] | 2025-10-10 |
| **Legal** | [Name] | 2025-10-10 |

---

**End of Security Incident Response Plan**
