# IP Range Management Guide
## Network Policy Security Configuration

**Last Updated:** 2025-01-27  
**Status:** Active  
**Compliance:** FedRAMP SC-7 (Network Security)

---

## Overview

This document provides guidance for managing IP address ranges (CIDR blocks) used in Kubernetes Network Policies and AWS Security Groups. Proper IP range management is critical for maintaining network security and FedRAMP compliance.

---

## Critical Security Requirement

**NEVER use `0.0.0.0/0` for egress rules in production environments** unless:
1. The service uses dynamic IP ranges that cannot be predicted
2. You have explicit approval from the security team
3. The rule includes proper exceptions for private networks

---

## Current IP Range Requirements

### 1. Anthropic Claude API ✅

**Status:** Configured  
**IP Ranges:**
- `52.84.0.0/15` (AWS us-east-1)
- `52.1.0.0/16` (AWS us-east-1 alternative)

**Source:** AWS IP ranges (Anthropic uses AWS infrastructure)  
**Last Verified:** 2025-01-27  
**Update Frequency:** Quarterly

**How to Update:**
```bash
# Download AWS IP ranges
curl -s https://ip-ranges.amazonaws.com/ip-ranges.json | jq '.prefixes[] | select(.service=="EC2" and .region=="us-east-1") | .ip_prefix'
```

---

### 2. GitHub API ✅

**Status:** Configured  
**IP Ranges:**
- `140.82.112.0/20`
- `192.30.252.0/22`
- `185.199.108.0/22`

**Source:** [GitHub API Meta Endpoint](https://api.github.com/meta)  
**Last Verified:** 2025-01-27  
**Update Frequency:** Monthly

**How to Update:**
```bash
# Get current GitHub IP ranges
curl -s https://api.github.com/meta | jq '.api[]'
```

**Note:** GitHub publishes IP ranges via their Meta API. These ranges are relatively stable but should be checked monthly.

---

### 3. Observo.ai API ⚠️

**Status:** **REQUIRES UPDATE**  
**Current Configuration:** `0.0.0.0/0` (TEMPORARY - SECURITY RISK)  
**Base URL:** `https://p01-api.observo.ai`

**Action Required:**
1. Contact Observo.ai support to obtain official IP ranges
2. Email: support@observo.ai
3. Request: "Please provide CIDR blocks for p01-api.observo.ai endpoint"

**Temporary Workaround:**
- Current configuration uses `0.0.0.0/0` with exceptions for private networks
- This is acceptable for development/testing only
- **MUST be updated before production deployment**

**How to Discover IP Ranges (if vendor doesn't provide):**
```bash
# Resolve DNS and check IP ranges
dig +short p01-api.observo.ai
nslookup p01-api.observo.ai

# Note: DNS resolution may return multiple IPs or use CDN
# Always verify with vendor for official ranges
```

**Update Procedure:**
1. Obtain IP ranges from Observo.ai
2. Update `deployment/k8s/base/networkpolicy.yaml` line 115
3. Update this document with verified ranges
4. Test connectivity
5. Deploy to production

---

### 4. SentinelOne SDL API ⚠️

**Status:** **REQUIRES UPDATE**  
**Current Configuration:** `0.0.0.0/0` (TEMPORARY - SECURITY RISK)  
**Base URL:** `https://xdr.us1.sentinelone.net` (US1 region)

**Action Required:**
1. Contact SentinelOne support to obtain official IP ranges
2. Portal: https://support.sentinelone.com
3. Request: "Please provide CIDR blocks for xdr.us1.sentinelone.net SDL API endpoint"

**Regional Endpoints:**
- US1: `xdr.us1.sentinelone.net`
- EU1: `xdr.eu1.sentinelone.net`
- AP1: `xdr.ap1.sentinelone.net`

**Temporary Workaround:**
- Current configuration uses `0.0.0.0/0` with exceptions for private networks
- This is acceptable for development/testing only
- **MUST be updated before production deployment**

**How to Discover IP Ranges (if vendor doesn't provide):**
```bash
# Resolve DNS and check IP ranges
dig +short xdr.us1.sentinelone.net
nslookup xdr.us1.sentinelone.net

# Note: SentinelOne uses CDN, so IPs may change
# Always verify with vendor for official ranges
```

**Update Procedure:**
1. Obtain IP ranges from SentinelOne
2. Update `deployment/k8s/base/networkpolicy.yaml` line 131
3. Update this document with verified ranges
4. Test connectivity
5. Deploy to production

---

## IP Range Update Process

### Step 1: Obtain Official IP Ranges

**Preferred Method:** Contact vendor support
- Most vendors provide official IP range documentation
- Request CIDR blocks in writing
- Keep documentation for audit purposes

**Alternative Method:** DNS Resolution (less reliable)
```bash
# Resolve hostname
dig +short api.example.com

# Check if using CDN (Cloudflare, AWS CloudFront, etc.)
curl -I https://api.example.com | grep -i "server\|cf-ray\|x-amz"

# For CDN services, you MUST contact vendor for official ranges
```

### Step 2: Validate IP Ranges

```bash
# Test connectivity with specific IP
curl -v --resolve api.example.com:443:1.2.3.4 https://api.example.com/health

# Verify CIDR block format
# Valid: 192.168.1.0/24
# Invalid: 192.168.1.0 (missing /CIDR)
```

### Step 3: Update Network Policy

1. Edit `deployment/k8s/base/networkpolicy.yaml`
2. Replace `0.0.0.0/0` with specific CIDR blocks
3. Add multiple `ipBlock` entries if needed
4. Keep `except` blocks for private networks

**Example:**
```yaml
- to:
    - ipBlock:
        cidr: 203.0.113.0/24  # Vendor IP range
        except:
          - 169.254.169.254/32  # AWS metadata
          - 127.0.0.0/8         # Loopback
          - 10.0.0.0/8          # Private network A
          - 172.16.0.0/12       # Private network B
          - 192.168.0.0/16      # Private network C
  ports:
    - protocol: TCP
      port: 443
```

### Step 4: Test Connectivity

```bash
# Apply network policy
kubectl apply -f deployment/k8s/base/networkpolicy.yaml

# Test from pod
kubectl exec -it <pod-name> -n purple-pipeline -- curl -v https://api.example.com/health

# Check network policy logs
kubectl logs -n kube-system -l app=calico-kube-controllers | grep <pod-name>
```

### Step 5: Update Documentation

1. Update this document with verified IP ranges
2. Update `REPOSITORY_ANALYSIS_REPORT.md` status
3. Update `RED_TEAM_SECURITY_ANALYSIS.md` if applicable
4. Create change log entry

---

## Security Best Practices

### 1. Principle of Least Privilege

- Only allow egress to IP ranges that are absolutely necessary
- Use specific CIDR blocks, not broad ranges
- Regularly review and tighten IP ranges

### 2. Exception Handling

Always exclude private network ranges:
- `169.254.169.254/32` - AWS metadata service (prevents SSRF)
- `127.0.0.0/8` - Loopback addresses
- `10.0.0.0/8` - Private network A
- `172.16.0.0/12` - Private network B
- `192.168.0.0/16` - Private network C
- `224.0.0.0/4` - Multicast
- `240.0.0.0/4` - Reserved

### 3. Monitoring

- Monitor network policy violations
- Alert on unexpected egress attempts
- Review egress logs regularly

### 4. Documentation

- Document all IP ranges and their sources
- Keep vendor communications for audit
- Update documentation when ranges change

---

## Compliance Requirements

### FedRAMP SC-7 (Network Security)

**Requirement:** "The information system monitors and controls communications at the external boundary of the system and at key internal boundaries within the system."

**Implementation:**
- ✅ Network policies restrict egress to specific IP ranges
- ✅ Exceptions prevent SSRF attacks
- ✅ Documentation provides audit trail
- ⚠️ Pending: Observo.ai and SentinelOne IP ranges

### NIST 800-53 SC-7(3)

**Requirement:** "The organization limits the number of external network connections to the information system."

**Implementation:**
- ✅ Only necessary external APIs allowed
- ✅ IP ranges documented and justified
- ✅ Regular review process established

---

## Emergency Procedures

### If IP Ranges Change Unexpectedly

1. **Immediate:** Temporarily allow `0.0.0.0/0` with exceptions (development only)
2. **Short-term:** Contact vendor for updated ranges
3. **Long-term:** Update network policy and test

### If Connectivity Fails

1. Check network policy logs
2. Verify DNS resolution
3. Test connectivity from pod
4. Review IP range exceptions
5. Contact vendor if ranges changed

---

## Change Log

| Date | Service | Change | Updated By |
|------|---------|--------|------------|
| 2025-01-27 | Anthropic | Initial configuration | Security Team |
| 2025-01-27 | GitHub | Initial configuration | Security Team |
| 2025-01-27 | Observo.ai | Documented requirement | Security Team |
| 2025-01-27 | SentinelOne | Documented requirement | Security Team |

---

## References

- [Kubernetes Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [AWS IP Ranges](https://docs.aws.amazon.com/general/latest/gr/aws-ip-ranges.html)
- [GitHub API Meta](https://api.github.com/meta)
- [FedRAMP SC-7 Control](https://www.fedramp.gov/)
- [NIST 800-53 SC-7](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)

---

## Contact Information

**Security Team:**
- Email: security@your-domain.com
- Slack: #security-team

**Vendor Contacts:**
- Observo.ai: support@observo.ai
- SentinelOne: https://support.sentinelone.com

---

**Document Owner:** Security Team  
**Review Frequency:** Quarterly  
**Next Review:** 2025-04-27

