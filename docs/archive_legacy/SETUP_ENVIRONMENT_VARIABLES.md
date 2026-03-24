# Environment Variables Setup Guide

**Status**: 🔴 ACTION REQUIRED
**Date**: 2025-11-07
**Purpose**: Configure mandatory environment variables for Web UI authentication and optional dataplane binary

---

## 🚨 Critical: Web UI Authentication Token

### What Needs to be Done

The Web UI **REQUIRES** the `WEB_UI_AUTH_TOKEN` environment variable to be set before startup. The application will **NOT** start without it.

**Current Status**:
- ✅ Code enforces mandatory authentication (components/web_feedback_ui.py:110-117)
- ✅ Configuration template prepared (config.yaml:52)
- 🔴 Environment variable **NOT YET SET**

### Step 1: Generate Security Token

Choose your platform:

#### **Windows (PowerShell or CMD)**
```powershell
# PowerShell
python -c "import secrets; print(secrets.token_urlsafe(32))"

# OR use openssl if available
openssl rand -base64 32
```

#### **Linux/macOS (Bash)**
```bash
# Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# OR use openssl
openssl rand -base64 32
```

**Example Output**:
```
AbCd1234-efGh5678-ijKl9012-mnOp3456-qrSt7890-uvWx1234-yzAb5678-cdef-EXAMPLE
```

### Step 2: Set Environment Variable

#### **Windows - Permanent (Recommended)**

**Option A: Environment Variables UI**
1. Press `Win + R`
2. Type `sysdm.cpl` and press Enter
3. Click "Advanced" tab
4. Click "Environment Variables"
5. Under "User variables", click "New"
6. Variable name: `WEB_UI_AUTH_TOKEN`
7. Variable value: `<paste-your-generated-token>`
8. Click OK and restart terminal/IDE

**Option B: CMD (Session Only)**
```cmd
set WEB_UI_AUTH_TOKEN=<your-generated-token>
python main.py
```

**Option C: PowerShell (Session Only)**
```powershell
$env:WEB_UI_AUTH_TOKEN="<your-generated-token>"
python main.py
```

#### **Linux/macOS - Terminal**

**Option A: Export in Session**
```bash
export WEB_UI_AUTH_TOKEN="<your-generated-token>"
python main.py
```

**Option B: Add to ~/.bashrc or ~/.zshrc**
```bash
echo 'export WEB_UI_AUTH_TOKEN="<your-generated-token>"' >> ~/.bashrc
source ~/.bashrc
python main.py
```

**Option C: Use .env file (if you create one)**
```bash
# Create .env file
echo 'WEB_UI_AUTH_TOKEN=<your-generated-token>' > .env

# Load it before running
set -a; source .env; set +a
python main.py
```

### Step 3: Verify Setup

**Test 1: Check Environment Variable is Set**

Windows (PowerShell):
```powershell
$env:WEB_UI_AUTH_TOKEN
# Should print your token
```

Windows (CMD):
```cmd
echo %WEB_UI_AUTH_TOKEN%
# Should print your token
```

Linux/macOS:
```bash
echo $WEB_UI_AUTH_TOKEN
# Should print your token
```

**Test 2: Start Application**
```bash
python main.py
# Should start without "authentication token is required" error
```

**Test 3: Access Web UI**

Once running, the Web UI will be available at `http://localhost:8080/` (or configured host:port)

To test with curl:
```bash
curl -H "X-PPPE-Token: <your-token>" http://localhost:8080/

# Expected response: 200 OK with HTML content
# OR: 401 Unauthorized if token is missing/invalid
```

---

## Optional: Other Environment Variables

### API Keys (Required if using external services)

```bash
# Anthropic Claude API Key
export ANTHROPIC_API_KEY="sk-ant-..."

# Observo.ai API Key (optional, defaults to dry-run-mode)
export OBSERVO_API_KEY="obs-..."

# GitHub Token (if accessing private repos)
export GITHUB_TOKEN="ghp_..."

# SentinelOne SDL API Key (if audit logging enabled)
export SDL_API_KEY="..."
```

### Dataplane Binary (Optional)

If deploying dataplane binary instead of Lupa:

**Linux/macOS**:
```bash
export DATAPLANE_BINARY_PATH="/opt/dataplane/dataplane"
```

**Windows**:
```cmd
set DATAPLANE_BINARY_PATH=C:\opt\dataplane\dataplane.exe
```

### Flask Security (Optional)

```bash
# Generate with: python -c "import os; print(os.urandom(32).hex())"
export FLASK_SECRET_KEY="<your-hex-key>"

# Custom Web UI host (default: 127.0.0.1)
export WEB_UI_HOST="0.0.0.0"  # For Docker
```

---

## Environment Variable File Template

Create `.env` file in repository root:

```bash
# .env (DO NOT COMMIT THIS FILE - Add to .gitignore)

# REQUIRED
ANTHROPIC_API_KEY="sk-ant-..."
WEB_UI_AUTH_TOKEN="<your-generated-token>"

# OPTIONAL
OBSERVO_API_KEY="obs-..."
GITHUB_TOKEN="ghp_..."
SDL_API_KEY="..."

# OPTIONAL: Dataplane
DATAPLANE_BINARY_PATH="/opt/dataplane/dataplane"

# OPTIONAL: Flask
FLASK_SECRET_KEY="..."
WEB_UI_HOST="127.0.0.1"
```

**Load with**:
```bash
# Linux/macOS
set -a; source .env; set +a
python main.py

# Windows PowerShell
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2])
    }
}
python main.py
```

---

## Configuration Reference

### Web UI Section (config.yaml)

```yaml
# config.yaml lines 48-53

web_ui:
  enabled: true
  host: "127.0.0.1"  # Localhost only by default (secure)
  port: 8080
  auth_token: "${WEB_UI_AUTH_TOKEN}"  # REQUIRED: Set environment variable above
  token_header: "X-PPPE-Token"         # HTTP header for authentication
```

### How Configuration Works

The `${WEB_UI_AUTH_TOKEN}` syntax means:
- **Load** the value from environment variable `WEB_UI_AUTH_TOKEN`
- **Error** if environment variable not set and no default provided
- **Always required** for Web UI to start (mandatory security)

---

## Troubleshooting

### Error: "Web UI authentication token is required for security"

**Cause**: `WEB_UI_AUTH_TOKEN` environment variable not set

**Solution**:
1. Generate token: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Set environment variable (see Step 2 above)
3. Restart application: `python main.py`

### Error: "Unauthorized access attempt" when accessing Web UI

**Cause**: Either:
- No token header provided in request
- Token header name is wrong (should be `X-PPPE-Token`)
- Token value doesn't match

**Solution**:
1. Verify environment variable is set: `echo $WEB_UI_AUTH_TOKEN`
2. Include correct header in request: `curl -H "X-PPPE-Token: <token>" http://localhost:8080/`
3. Check logs: `tail -f logs/runtime_service.log | grep -i auth`

### Error: 401 Unauthorized even with token

**Cause**: Token value doesn't match what was set

**Solution**:
1. Get your token: `echo $WEB_UI_AUTH_TOKEN`
2. Verify it matches in request headers
3. Regenerate if uncertain: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

---

## Security Best Practices

✅ **DO:**
- Generate strong random tokens (use `secrets.token_urlsafe()`)
- Store tokens in environment variables, not in code
- Use different tokens for different environments (dev, staging, prod)
- Rotate tokens regularly in production
- Use HTTPS/TLS in production (enable in config.yaml)
- Don't commit .env files to git

❌ **DON'T:**
- Use default tokens or hardcoded values
- Store tokens in config.yaml (use environment variables)
- Share tokens via chat, email, or version control
- Use same token across multiple environments
- Disable authentication (code prevents this)

---

## Next Steps

1. ✅ Generate Web UI authentication token (see Step 1)
2. ✅ Set environment variable (see Step 2)
3. ✅ Verify setup works (see Step 3)
4. 🔄 Optional: Deploy dataplane binary (see DATAPLANE_SETUP.md)
5. 🚀 Start application: `python main.py`

---

**Status**: Ready for implementation
**Time to Complete**: 5 minutes for Web UI authentication
**Blocking**: None (application will fail to start without WEB_UI_AUTH_TOKEN)

