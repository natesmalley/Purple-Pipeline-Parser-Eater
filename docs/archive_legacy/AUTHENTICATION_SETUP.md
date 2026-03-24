# 🔐 Authentication Setup Guide

## Overview

Purple Pipeline Parser Eater requires authentication for all API operations. This guide walks you through setting up authentication for development, testing, and production environments.

## Table of Contents

1. [Required Authentication](#required-authentication)
2. [Environment Variables](#environment-variables)
3. [Web UI Authentication](#web-ui-authentication)
4. [API Authentication](#api-authentication)
5. [Security Best Practices](#security-best-practices)
6. [Troubleshooting](#troubleshooting)

---

## Required Authentication

### Mandatory Components

The following are **REQUIRED** for all installations:

| Component | Purpose | Source |
|-----------|---------|--------|
| `ANTHROPIC_API_KEY` | Claude AI analysis and transformation | https://console.anthropic.com/ |
| `WEB_UI_AUTH_TOKEN` | Web UI access authentication | Generate locally |

### Optional Components

The following are **OPTIONAL** depending on your use case:

| Component | Purpose | Source |
|-----------|---------|--------|
| `GITHUB_TOKEN` | GitHub integration | https://github.com/settings/tokens |
| `OBSERVO_API_TOKEN` | Observo.ai integration | Observo.ai dashboard |
| `AWS_*` | AWS S3 integration | AWS IAM Console |

---

## Environment Variables

### Setup .env File

**Step 1: Copy Template**

```bash
cp .env.example .env
```

**Step 2: Edit .env**

```bash
# Edit the file with your preferred editor
nano .env
# or
vim .env
```

**Step 3: Set Permissions (Linux/Mac)**

```bash
chmod 600 .env
```

### Required Variables

#### ANTHROPIC_API_KEY

```bash
# Get from https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-... # Replace with your actual key
```

**How to Get:**
1. Go to https://console.anthropic.com/
2. Sign in with your Anthropic account
3. Navigate to "API keys" section
4. Click "Create Key"
5. Copy the generated key (starts with `sk-ant-`)

#### WEB_UI_AUTH_TOKEN

```bash
# Generate a secure token
WEB_UI_AUTH_TOKEN=your-secure-token-here
```

**How to Generate:**

```bash
# Option 1: Python
python -c "import secrets; print(secrets.token_hex(32))"

# Option 2: OpenSSL
openssl rand -hex 32

# Option 3: Linux /dev/urandom
head -c 32 /dev/urandom | xxd -p
```

**Requirements:**
- Minimum 32 characters
- Use only alphanumeric characters
- Must be unique per installation
- Store securely (never commit to git)

---

## Web UI Authentication

### Login Token

The Web UI uses token-based authentication for all requests.

**Default Behavior:**
- Token is required for all API endpoints
- Token is passed in `Authorization` header
- Format: `Authorization: Bearer {WEB_UI_AUTH_TOKEN}`

### Using Web UI

**Step 1: Navigate to Web UI**

```
http://localhost:5000
```

**Step 2: Authenticate**

When prompted, enter your `WEB_UI_AUTH_TOKEN`

**Step 3: Access Protected Features**

Once authenticated, you have access to:
- Parser management
- Conversion monitoring
- Metrics and analytics
- System settings

### API Token Management

**Get Current Token:**
```bash
echo $WEB_UI_AUTH_TOKEN
```

**Rotate Token (Create New):**

```bash
# Generate new token
NEW_TOKEN=$(python -c "import secrets; print(secrets.token_hex(32))")

# Update .env
sed -i "s/WEB_UI_AUTH_TOKEN=.*/WEB_UI_AUTH_TOKEN=$NEW_TOKEN/" .env

# Restart service
# (Specific restart method depends on deployment)
```

---

## API Authentication

### Header Format

All API requests must include authentication header:

```http
GET /api/v1/status HTTP/1.1
Host: localhost:5000
Authorization: Bearer your-web-ui-auth-token
```

### Example Requests

**Using cURL:**
```bash
curl -H "Authorization: Bearer $WEB_UI_AUTH_TOKEN" \
  http://localhost:5000/api/v1/status
```

**Using Python requests:**
```python
import requests

headers = {
    "Authorization": f"Bearer {os.getenv('WEB_UI_AUTH_TOKEN')}"
}

response = requests.get(
    "http://localhost:5000/api/v1/status",
    headers=headers
)
```

**Using JavaScript fetch:**
```javascript
const token = process.env.WEB_UI_AUTH_TOKEN;

fetch('http://localhost:5000/api/v1/status', {
    headers: {
        'Authorization': `Bearer ${token}`
    }
})
.then(r => r.json())
.then(data => console.log(data));
```

### Authentication Error Codes

| Code | Message | Solution |
|------|---------|----------|
| 401 | Unauthorized | Token missing or invalid |
| 403 | Forbidden | Token valid but insufficient permissions |
| 400 | Bad Request | Missing Authorization header |

---

## Security Best Practices

### Do's ✅

- ✅ Use strong, random tokens (32+ characters)
- ✅ Store tokens in `.env` file (not in code)
- ✅ Add `.env` to `.gitignore` (already done)
- ✅ Rotate tokens regularly (monthly recommended)
- ✅ Use HTTPS in production
- ✅ Restrict `.env` file permissions: `chmod 600`
- ✅ Never log sensitive values
- ✅ Use different tokens for different environments

### Don'ts ❌

- ❌ Never commit `.env` to git
- ❌ Don't use weak or predictable tokens
- ❌ Don't share tokens via email
- ❌ Don't log API keys
- ❌ Don't use same token across environments
- ❌ Don't expose tokens in client-side code
- ❌ Don't leave default tokens in production

### Environment-Specific Tokens

**Development:**
```bash
# Can be less restrictive
WEB_UI_AUTH_TOKEN=dev-token-for-testing
```

**Staging:**
```bash
# Use strong random token
WEB_UI_AUTH_TOKEN=$(python -c "import secrets; print(secrets.token_hex(32))")
```

**Production:**
```bash
# Use AWS Secrets Manager or similar
# Set via environment, never in .env file
export WEB_UI_AUTH_TOKEN=$(aws secretsmanager get-secret-value ...)
```

---

## Troubleshooting

### Issue: "Invalid API Key" Error

**Cause:** ANTHROPIC_API_KEY is incorrect or expired

**Solution:**
```bash
# 1. Verify the key in .env
grep ANTHROPIC_API_KEY .env

# 2. Get a new key from https://console.anthropic.com/

# 3. Update .env
nano .env

# 4. Restart service
# (Specific command depends on deployment)
```

### Issue: "Authentication Failed" on Web UI

**Cause:** WEB_UI_AUTH_TOKEN is missing or incorrect

**Solution:**
```bash
# 1. Check token is set
echo $WEB_UI_AUTH_TOKEN

# 2. If empty, verify .env is loaded
cat .env | grep WEB_UI_AUTH_TOKEN

# 3. Generate new token if needed
python -c "import secrets; print(secrets.token_hex(32))"

# 4. Update .env and restart
```

### Issue: "Token Not Found" in API Calls

**Cause:** Authorization header not sent correctly

**Solution:**
```bash
# Test with proper header format
curl -v \
  -H "Authorization: Bearer $WEB_UI_AUTH_TOKEN" \
  http://localhost:5000/api/v1/status

# Verify header is present
# Look for: > Authorization: Bearer ...
```

### Issue: Token Expired

**Cause:** Token was rotated or invalidated

**Solution:**
```bash
# 1. Generate new token
NEW_TOKEN=$(python -c "import secrets; print(secrets.token_hex(32))")

# 2. Update environment
export WEB_UI_AUTH_TOKEN=$NEW_TOKEN

# 3. Or update .env
echo "WEB_UI_AUTH_TOKEN=$NEW_TOKEN" >> .env

# 4. Verify
echo $WEB_UI_AUTH_TOKEN
```

---

## Multi-Environment Setup

### Development (.env.development)

```bash
# Quick setup for development
ANTHROPIC_API_KEY=sk-ant-dev-key
WEB_UI_AUTH_TOKEN=dev-token-short-for-testing
WEB_UI_DEBUG=true
APP_ENV=development
```

### Testing (.env.test)

```bash
# Automated testing
ANTHROPIC_API_KEY=sk-ant-test-key
WEB_UI_AUTH_TOKEN=test-token-for-ci-cd
TESTING_MODE=true
APP_ENV=testing
```

### Production (.env.production)

```bash
# Production deployment
# NOTE: Never commit this file!
# Use environment variables or secrets manager instead

ANTHROPIC_API_KEY=sk-ant-prod-key-secure
WEB_UI_AUTH_TOKEN=prod-token-strong-random-string
WEB_UI_DEBUG=false
APP_ENV=production
```

### Switching Environments

```bash
# Development
cp .env.development .env

# Testing
cp .env.test .env

# Production (use env vars, not file)
export ANTHROPIC_API_KEY=...
export WEB_UI_AUTH_TOKEN=...
```

---

## Integration with CI/CD

### GitHub Actions

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set environment
        run: |
          echo "ANTHROPIC_API_KEY=${{ secrets.ANTHROPIC_API_KEY }}" >> .env
          echo "WEB_UI_AUTH_TOKEN=${{ secrets.WEB_UI_AUTH_TOKEN }}" >> .env

      - name: Run tests
        run: pytest tests/
```

### GitLab CI

```yaml
test:
  stage: test
  script:
    - echo "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" > .env
    - echo "WEB_UI_AUTH_TOKEN=$WEB_UI_AUTH_TOKEN" >> .env
    - pytest tests/
  only:
    - merge_requests
```

---

## Reference

### Configuration Checklist

- [ ] Copy `.env.example` to `.env`
- [ ] Set `ANTHROPIC_API_KEY` from https://console.anthropic.com/
- [ ] Generate and set `WEB_UI_AUTH_TOKEN`
- [ ] Set file permissions: `chmod 600 .env`
- [ ] Add `.env` to `.gitignore` (already done)
- [ ] Test authentication: `curl -H "Authorization: Bearer $WEB_UI_AUTH_TOKEN" http://localhost:5000/api/v1/status`
- [ ] Never commit `.env` to git
- [ ] Rotate tokens regularly in production

### Security Checklist

- [ ] All tokens are 32+ characters
- [ ] Tokens use cryptographically secure randomness
- [ ] Different tokens for different environments
- [ ] File permissions restrict unauthorized access
- [ ] No tokens in logs or error messages
- [ ] Tokens rotated monthly (production)
- [ ] Secrets manager used in production
- [ ] API tokens validated on every request

---

**Next Steps:**
- Complete authentication setup
- Follow [SETUP.md](SETUP.md) for full installation
- Check [README.md](../README.md) for usage examples
