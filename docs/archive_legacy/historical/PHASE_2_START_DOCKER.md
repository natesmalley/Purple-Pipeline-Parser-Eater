# Phase 2: Start Docker Desktop

**Current Status**: Docker is installed but not running
**Required Action**: Manual start of Docker Desktop application

---

## Why Docker Desktop Needs to Be Running

The RAG system uses **Milvus vector database** which runs in Docker containers along with:
- **Milvus**: Vector database engine (stores embeddings)
- **etcd**: Metadata storage for Milvus
- **MinIO**: Object storage for Milvus data

All three services are orchestrated via `docker-compose.yml` and require Docker Desktop to be running.

---

## Step-by-Step Instructions

### Option 1: Start from Windows Start Menu (Easiest)

1. Press `Windows` key
2. Type "Docker Desktop"
3. Click "Docker Desktop" application
4. Wait 30-60 seconds for Docker to fully start
5. Look for Docker whale icon in system tray (bottom-right)

### Option 2: Start from Command Line

```powershell
# Start Docker Desktop
start "C:\Program Files\Docker\Docker\Docker Desktop.exe"
```

Then wait 30-60 seconds for startup.

### Option 3: Start from File Explorer

1. Open File Explorer
2. Navigate to: `C:\Program Files\Docker\Docker\`
3. Double-click `Docker Desktop.exe`
4. Wait 30-60 seconds

---

## Verification Steps

Once Docker Desktop is running, verify with:

```bash
# Should show: CONTAINER ID   IMAGE   COMMAND   CREATED   STATUS   PORTS   NAMES
docker ps

# Should show: Client and Server version info
docker version

# Should show: Containers, Images, Server Version
docker info
```

**Expected Output** (when working):
```
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
(empty list is OK - no containers running yet)
```

**Current Error** (Docker not running):
```
error during connect: ... The system cannot find the file specified
```

---

## Common Issues

### Issue 1: Docker Desktop Won't Start
**Symptoms**: Application opens but closes immediately
**Solutions**:
- Check Windows version (Windows 10 Pro/Enterprise/Education or Windows 11)
- Enable Hyper-V and WSL2 in Windows Features
- Restart computer
- Reinstall Docker Desktop

### Issue 2: "Docker is starting..." Takes Forever
**Symptoms**: Stuck on startup screen
**Solutions**:
- Wait 2-3 minutes (can be slow on first start)
- Close Docker Desktop and restart
- Check Task Manager - kill any stuck `Docker Desktop.exe` processes
- Restart computer

### Issue 3: WSL2 Errors
**Symptoms**: Error about WSL2 kernel or distribution
**Solutions**:
```powershell
# Update WSL2
wsl --update

# Set WSL2 as default
wsl --set-default-version 2

# List WSL distributions
wsl --list --verbose
```

### Issue 4: "Access Denied" or Permission Errors
**Symptoms**: Can't start Docker Desktop
**Solutions**:
- Run Docker Desktop as Administrator
- Add your user to "docker-users" group:
  1. Open "Computer Management"
  2. Navigate to "Local Users and Groups" > "Groups"
  3. Double-click "docker-users"
  4. Add your username
  5. Log out and log back in

---

## Next Steps

Once `docker ps` runs successfully without errors:

**Proceed to Phase 3**: Install Python RAG packages
```bash
pip install torch pymilvus sentence-transformers
```

---

## Time Estimate

- Starting Docker Desktop: 30-60 seconds
- Troubleshooting (if needed): 5-15 minutes
- Total: 1-15 minutes

---

**Status**: ⏳ WAITING FOR USER ACTION - Please start Docker Desktop
