# Dataplane Binary Setup Guide

**Status**: 🔴 SETUP REQUIRED
**Date**: 2025-11-07
**Purpose**: Deploy Observo dataplane binary for production-ready transform execution

---

## Overview

The **Dataplane Binary** is Observo's production-grade event transformation executor. It provides:

- **Isolated Execution**: Runs in separate subprocess (safe process isolation)
- **Production Parity**: Same execution engine as Observo.ai production
- **OCSF Validation**: Built-in security event schema validation
- **Error Containment**: Crashes isolated to subprocess, won't crash main application
- **Resource Control**: Can limit memory/CPU per transform operation

**Current Status**:
- ⚠️ Binary is no longer bundled in this repository; provide it via external artifact/source path
- ✅ Code integration ready: `DataplaneExecutor` class implemented in `components/transform_executor.py`
- 🔴 Binary NOT deployed to `/opt/dataplane/dataplane` (required location)
- 🔴 Configuration NOT enabled (currently uses Lupa in-process executor)

---

## Architecture

### Current Setup (Lupa - In-Process)

```
User Request
    ↓
Main Process (Python)
    ↓
Lupa VM (in-process)
    ↓
Transform Result
    └─ Risk: Lupa crash = entire process crash
```

**Advantages**:
- ✅ Fast (no subprocess overhead)
- ✅ Easy to debug (same process)
- ✅ No external dependencies

**Disadvantages**:
- ❌ In-process = unsafe (crashes affect main app)
- ❌ Limited error isolation
- ❌ No production parity

### New Setup (Dataplane - Subprocess)

```
User Request
    ↓
Main Process (Python)
    ↓
DataplaneExecutor
    ├─ Spawn subprocess with `/opt/dataplane/dataplane`
    ├─ Pass transform code + event data
    └─ Receive validated result

    └─ Safety: Dataplane crash = subprocess dies, main continues
```

**Advantages**:
- ✅ Safe subprocess isolation
- ✅ Production parity with Observo.ai
- ✅ OCSF schema validation built-in
- ✅ Resource control (memory/CPU limits)
- ✅ Better error handling

**Disadvantages**:
- ❌ Slight overhead (subprocess creation)
- ❌ Harder to debug (separate process)
- ❌ Requires binary deployment

---

## Prerequisites

### System Requirements

**Linux (Recommended for Production)**:
- x86-64 (amd64) or ARM64 (aarch64) architecture
- `/opt` directory writable (or use alternate path with DATAPLANE_BINARY_PATH)
- Sufficient disk space (~50MB for binary)

**macOS**:
- x86-64 or ARM64 (M1/M2/M3 Apple Silicon)
- `/opt` directory (may need to create with `sudo`)

**Windows**:
- Only works in WSL2 (Windows Subsystem for Linux)
- Or use Docker with dataplane baked in

### Binary Availability

The binary is not included in this repository. Provide an external binary artifact:

```
/path/to/dataplane.amd64    ← For AMD64/x86-64 systems
/path/to/dataplane.aarch64  ← For ARM64/aarch64 systems
```

---

## Installation Steps

### Step 1: Determine Your Architecture

**Linux/macOS**:
```bash
uname -m
# Output examples:
# x86_64    → Use dataplane.amd64
# aarch64   → Use dataplane.aarch64
# arm64     → Use dataplane.aarch64 (macOS M1/M2)
```

**Windows (WSL2)**:
```bash
uname -m
# Same as above in WSL2
```

### Step 2: Create /opt/dataplane Directory

**Linux/macOS**:
```bash
sudo mkdir -p /opt/dataplane
sudo chmod 755 /opt/dataplane
```

**Windows (WSL2)**:
```bash
sudo mkdir -p /opt/dataplane
```

### Step 3: Deploy Binary

**Option A: Install via Helper Script (Recommended)**

For AMD64:
```bash
sudo ./scripts/install_dataplane.sh --binary-source /path/to/dataplane.amd64
```

For ARM64:
```bash
sudo ./scripts/install_dataplane.sh --binary-source /path/to/dataplane.aarch64
```

**Option B: Copy Manually (Flexible)**

```bash
# Copy amd64 or aarch64 binary from your external artifact source
sudo cp /path/to/dataplane.amd64 /opt/dataplane/dataplane
sudo chmod +x /opt/dataplane/dataplane
```

**Option C: Custom Location (Non-Standard)**

If `/opt/dataplane/` is not available:

```bash
# Use alternate location
export DATAPLANE_BINARY_PATH="/usr/local/bin/dataplane"
sudo cp /path/to/dataplane.amd64 /usr/local/bin/dataplane
sudo chmod +x /usr/local/bin/dataplane

# Update config.yaml to use this path
# See Step 4 below
```

### Step 4: Verify Binary

```bash
# Check file exists
ls -lh /opt/dataplane/dataplane

# Test binary execution
/opt/dataplane/dataplane --version
# Expected: Version information

# Test binary is executable
file /opt/dataplane/dataplane
# Expected: ELF 64-bit (AMD64 or ARM64)
```

### Step 5: Update Configuration

Edit `config.yaml` to enable dataplane:

**Before** (current - lines 131-141):
```yaml
dataplane:
  enabled: false           # Currently DISABLED
  binary_path: "/opt/dataplane/dataplane"
  max_events: 10
  timeout_seconds: 30

transform_worker:
  enabled: false
  executor: "lupa"         # Currently using Lupa
```

**After** (desired):
```yaml
dataplane:
  enabled: true            # ← ENABLE DATAPLANE
  binary_path: "/opt/dataplane/dataplane"
  max_events: 10
  timeout_seconds: 30

transform_worker:
  enabled: false
  executor: "dataplane"    # ← SWITCH TO DATAPLANE
```

**Command to Update**:

```bash
# Linux/macOS
sed -i 's/enabled: false/enabled: true/' config.yaml  # Enable dataplane
sed -i 's/executor: "lupa"/executor: "dataplane"/' config.yaml  # Switch executor

# Verify changes
grep -A2 "^dataplane:" config.yaml
grep -A2 "^transform_worker:" config.yaml
```

**Windows (PowerShell)**:
```powershell
# Edit config.yaml manually OR use:
$config = Get-Content config.yaml
$config = $config -replace 'dataplane:\s+enabled: false', 'dataplane:`n  enabled: true'
$config = $config -replace 'executor: "lupa"', 'executor: "dataplane"'
$config | Set-Content config.yaml
```

### Step 6: Test Dataplane Integration

**Test 1: Verify Binary is Accessible**

```bash
# Python test
python -c "
from components.transform_executor import DataplaneExecutor
try:
    executor = DataplaneExecutor('/opt/dataplane/dataplane')
    print('✓ Dataplane executor initialized successfully')
except Exception as e:
    print(f'✗ Dataplane executor failed: {e}')
"
```

**Test 2: Start Application with Dataplane**

```bash
# Start with debug logging
python main.py --log-level DEBUG

# Look for these log messages:
# [OK] Dataplane enabled
# [OK] Dataplane binary initialized: /opt/dataplane/dataplane
# ✓ Transform executor: DataplaneExecutor (isolated subprocess execution)
```

**Test 3: Check Logs for Dataplane Activity**

```bash
# Monitor dataplane interactions
tail -f logs/runtime_service.log | grep -i dataplane

# Expected output:
# [INFO] DataplaneExecutor: Spawning subprocess...
# [INFO] DataplaneExecutor: Transform completed successfully
```

---

## Docker Deployment

If you're using Docker, add dataplane setup to your Dockerfile:

### Single-Stage Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

# Install Python dependencies
RUN pip install -r requirements.txt

# Setup dataplane binary
RUN mkdir -p /opt/dataplane && \
    cp /path/to/dataplane.amd64 /opt/dataplane/dataplane && \
    chmod +x /opt/dataplane/dataplane && \
    /opt/dataplane/dataplane --version

# Setup environment for dataplane
ENV DATAPLANE_BINARY_PATH="/opt/dataplane/dataplane"

# Start application
CMD ["python", "main.py"]
```

### Multi-Stage Dockerfile (Recommended)

```dockerfile
# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app
COPY . .
RUN pip install --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy Python dependencies
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application
COPY --from=builder /app /app

# Setup dataplane binary
RUN mkdir -p /opt/dataplane && \
    cp /path/to/dataplane.amd64 /opt/dataplane/dataplane && \
    chmod +x /opt/dataplane/dataplane && \
    /opt/dataplane/dataplane --version

# Environment variables
ENV DATAPLANE_BINARY_PATH="/opt/dataplane/dataplane" \
    WEB_UI_AUTH_TOKEN="" \
    PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
```

### Docker Compose

```yaml
services:
  purple-pipeline:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - WEB_UI_AUTH_TOKEN=${WEB_UI_AUTH_TOKEN}
      - DATAPLANE_BINARY_PATH=/opt/dataplane/dataplane
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./logs:/app/logs
    ports:
      - "8080:8080"
    # Binary is included in image, no volume mount needed
```

---

## Kubernetes Deployment

For Kubernetes, use an init container to setup dataplane:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: purple-pipeline
spec:
  # Init container to setup dataplane binary
  initContainers:
  - name: setup-dataplane
    image: alpine:latest
    command:
      - sh
      - -c
      - |
        mkdir -p /opt/dataplane
        # Copy from ConfigMap or volume
        cp /repo-binary/dataplane.amd64 /opt/dataplane/dataplane
        chmod +x /opt/dataplane/dataplane
        echo "Dataplane binary setup complete"
    volumeMounts:
    - name: repo-binary
      mountPath: /repo-binary
    - name: dataplane-volume
      mountPath: /opt/dataplane

  # Main container
  containers:
  - name: purple-pipeline
    image: purple-pipeline:latest
    env:
    - name: WEB_UI_AUTH_TOKEN
      valueFrom:
        secretKeyRef:
          name: purple-secrets
          key: web-ui-token
    - name: DATAPLANE_BINARY_PATH
      value: /opt/dataplane/dataplane
    volumeMounts:
    - name: dataplane-volume
      mountPath: /opt/dataplane
    - name: logs
      mountPath: /app/logs

  # Volumes
  volumes:
  - name: repo-binary
    configMap:
      name: dataplane-binary
  - name: dataplane-volume
    emptyDir: {}
  - name: logs
    persistentVolumeClaim:
      claimName: logs-pvc
```

---

## Troubleshooting

### Error: "Binary not found at /opt/dataplane/dataplane"

**Cause**: Binary not deployed or wrong path

**Solution**:
```bash
# Check if binary exists
ls -l /opt/dataplane/dataplane

# If not, deploy it:
sudo cp /path/to/dataplane.amd64 /opt/dataplane/dataplane
sudo chmod +x /opt/dataplane/dataplane

# Or update config with correct path
export DATAPLANE_BINARY_PATH="/path/to/dataplane"
```

### Error: "Permission denied" when running binary

**Cause**: Binary not executable

**Solution**:
```bash
# Fix permissions
sudo chmod +x /opt/dataplane/dataplane

# Verify
ls -l /opt/dataplane/dataplane
# Should show: rwx r-x r-x (755)
```

### Error: "Wrong binary architecture"

**Cause**: Wrong binary for system architecture

**Solution**:
```bash
# Check your architecture
uname -m

# Deploy correct binary:
# x86_64 → use dataplane.amd64
# aarch64 or arm64 → use dataplane.aarch64

# Check binary architecture:
file /opt/dataplane/dataplane
# Should match your system
```

### Error: "Subprocess timeout"

**Cause**: Dataplane taking too long to process

**Solution**: Increase timeout in config.yaml:
```yaml
dataplane:
  timeout_seconds: 30  # Increase this (default: 30)
```

### Dataplane Not Loading

**Check logs**:
```bash
tail -f logs/runtime_service.log | grep -i dataplane

# Look for error messages like:
# ERROR: DataplaneExecutor: Binary not found
# ERROR: DataplaneExecutor: Timeout
# ERROR: DataplaneExecutor: Invalid response
```

---

## Performance Comparison

| Aspect | Lupa (In-Process) | Dataplane (Subprocess) |
|--------|-------------------|------------------------|
| **Speed** | ⚡ Very fast | 🚀 Fast (slight overhead) |
| **Isolation** | ❌ Same process | ✅ Separate process |
| **Production** | ⚠️ Development only | ✅ Production-ready |
| **Error Safety** | ❌ Crash affects app | ✅ Isolated crashes |
| **OCSF Validation** | ❌ Manual | ✅ Built-in |
| **Scalability** | ⚠️ Limited | ✅ Better (resource control) |
| **Debugging** | ✅ Easy (same process) | ⚠️ Harder (separate process) |

---

## Configuration Reference

**config.yaml - Dataplane Settings** (lines 131-141):

```yaml
dataplane:
  enabled: false              # Set to true to enable
  binary_path: "/opt/dataplane/dataplane"  # Absolute path required
  max_events: 10              # Max events per batch
  timeout_seconds: 30         # Subprocess timeout

  # OCSF schema validation
  ocsf_required_fields:       # Fields that must be present
    - class_uid
    - class_name
    - category_uid
    - metadata

transform_worker:
  enabled: false              # Optional, for future use
  executor: "lupa"            # Change to "dataplane" to use dataplane
```

**Environment Variables**:

```bash
# Override binary path
export DATAPLANE_BINARY_PATH="/custom/path/to/dataplane"

# Set in config at runtime (if using template engine)
# Not typically needed - config.yaml is primary source
```

---

## Next Steps

1. ✅ Deploy binary to `/opt/dataplane/dataplane` (Step 1-3 above)
2. ✅ Verify binary works (Step 4)
3. ✅ Update config.yaml (Step 5)
4. ✅ Test integration (Step 6)
5. 🚀 Start application: `python main.py`
6. 🔍 Monitor logs for dataplane activity

---

## Rollback (Revert to Lupa)

If you need to go back to Lupa in-process executor:

```bash
# Edit config.yaml and change back:
# dataplane.enabled: true → false
# transform_worker.executor: "dataplane" → "lupa"

# Or use sed:
sed -i 's/enabled: true/enabled: false/' config.yaml
sed -i 's/executor: "dataplane"/executor: "lupa"/' config.yaml

# Restart application
python main.py
```

---

**Status**: Documentation complete, ready for implementation
**Time to Complete**: 10-15 minutes for local setup, 20-30 minutes for production
**Recommended**: Dataplane for production, Lupa for local development
