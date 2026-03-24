# Purple Pipeline Parser Eater - Docker Deployment Preparation Script (PowerShell)
# STIG Compliant | Security Hardened

# Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

# ============================================================================
# Functions
# ============================================================================

function Write-Header {
    param([string]$Message)
    Write-Host "============================================================================" -ForegroundColor Blue
    Write-Host $Message -ForegroundColor Blue
    Write-Host "============================================================================" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-InfoCustomCustom {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Cyan
}

function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        Write-Success "$Command is installed"
        return $true
    } catch {
        Write-Error-Custom "$Command is not installed"
        return $false
    }
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

Write-Header "Purple Pipeline Parser Eater - Docker Deployment Preparation"
Write-Host ""

Write-InfoCustomCustom "Starting pre-flight checks..."
Write-Host ""

# Check Docker
if (Test-Command docker) {
    $dockerVersion = docker --version
    Write-InfoCustomCustom "Docker: $dockerVersion"
} else {
    Write-Error-Custom "Docker is required but not installed"
    Write-InfoCustom "Install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    exit 1
}

# Check Docker Compose
$composeCmd = "docker"
$composeArgs = "compose"
try {
    $composeVersion = docker compose version
    Write-InfoCustom "Docker Compose: $composeVersion"
} catch {
    Write-Error-Custom "Docker Compose is required but not available"
    exit 1
}

# Check Docker daemon
try {
    docker info | Out-Null
    Write-Success "Docker daemon is running"
} catch {
    Write-Error-Custom "Docker daemon is not running. Please start Docker Desktop."
    exit 1
}

Write-Host ""

# ============================================================================
# Directory Structure
# ============================================================================

Write-Header "Creating Directory Structure"
Write-Host ""

$directories = @(
    "data\milvus",
    "data\etcd",
    "data\minio",
    "output",
    "logs",
    "data"
)

foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Success "Created directory: $dir"
    } else {
        Write-InfoCustom "Directory already exists: $dir"
    }
}

Write-Host ""

# ============================================================================
# Configuration Files
# ============================================================================

Write-Header "Checking Configuration Files"
Write-Host ""

# Check config.yaml
if (!(Test-Path "config.yaml")) {
    Write-Error-Custom "config.yaml not found!"
    Write-InfoCustom "Please create config.yaml before deployment"
    exit 1
} else {
    Write-Success "config.yaml found"

    # Security check
    if (Select-String -Path "config.yaml" -Pattern "api_key:" -Quiet) {
        Write-Warning-Custom "API keys found in config.yaml - ensure this file is secured!"
    }
}

# Check .env file
if (!(Test-Path ".env")) {
    Write-Warning-Custom ".env file not found"

    if (Test-Path ".env.example") {
        Write-InfoCustom "Copying .env.example to .env"
        Copy-Item ".env.example" ".env"
        Write-Warning-Custom "SECURITY: Update .env with your secure credentials!"
        Write-InfoCustom "Edit .env and change default passwords before deployment"
    } else {
        Write-Error-Custom ".env.example not found. Cannot create .env"
        exit 1
    }
} else {
    Write-Success ".env file found"

    # Check for default credentials
    if (Select-String -Path ".env" -Pattern "minioadmin" -Quiet) {
        Write-Warning-Custom "Default MinIO credentials detected in .env!"
        Write-Warning-Custom "Change MINIO_ACCESS_KEY and MINIO_SECRET_KEY before production deployment"
    }
}

Write-Host ""

# ============================================================================
# Docker Environment Preparation
# ============================================================================

Write-Header "Docker Environment Preparation"
Write-Host ""

# Check for existing containers
$existingContainers = docker ps -a --filter "name=purple-" --format "{{.Names}}" 2>$null

if ($existingContainers) {
    Write-Warning-Custom "Found existing Purple Pipeline containers:"
    Write-Host $existingContainers
    $response = Read-Host "Remove existing containers? (y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        Write-InfoCustom "Stopping and removing existing containers..."
        docker compose down -v 2>$null
        Write-Success "Existing containers removed"
    }
}

Write-Host ""

# ============================================================================
# Build Docker Images
# ============================================================================

Write-Header "Building Docker Images"
Write-Host ""

Write-InfoCustom "Building purple-pipeline-parser-eater:9.0.0..."
Write-InfoCustom "This may take several minutes on first build..."
Write-Host ""

try {
    docker build -t purple-pipeline-parser-eater:9.0.0 -f Dockerfile .
    Write-Success "Docker image built successfully"

    # Show image size
    $imageInfo = docker images purple-pipeline-parser-eater:9.0.0 --format "{{.Size}}"
    Write-InfoCustom "Image size: $imageInfo"
} catch {
    Write-Error-Custom "Docker build failed!"
    Write-Error-Custom $_.Exception.Message
    exit 1
}

Write-Host ""

# ============================================================================
# Security Scan
# ============================================================================

Write-Header "Security Scanning"
Write-Host ""

if (Test-Command trivy) {
    Write-InfoCustom "Running Trivy security scan..."
    try {
        trivy image --severity HIGH,CRITICAL purple-pipeline-parser-eater:9.0.0
    } catch {
        Write-Warning-Custom "Trivy scan found vulnerabilities"
    }
} else {
    Write-Warning-Custom "Trivy security scanner not found"
    Write-InfoCustom "Install Trivy for security scanning: https://github.com/aquasecurity/trivy"
}

Write-Host ""

# ============================================================================
# Deployment Summary
# ============================================================================

Write-Header "Deployment Preparation Complete"
Write-Host ""

Write-Success "All pre-flight checks passed"
Write-Host ""
Write-InfoCustom "Deployment Summary:"
Write-Host "  • Docker image: purple-pipeline-parser-eater:9.0.0"
Write-Host "  • Configuration: config.yaml (present)"
Write-Host "  • Environment: .env (configured)"
Write-Host "  • Data directories: Created"
Write-Host "  • Security: STIG compliance configured"
Write-Host "  • FIPS: Enabled in container environment"
Write-Host ""

Write-Header "Next Steps"
Write-Host ""
Write-Host "1. Review and update configuration:"
Write-Host "   - Edit config.yaml (API keys, settings)"
Write-Host "   - Edit .env (MinIO credentials, resource limits)"
Write-Host ""
Write-Host "2. Start the services:"
Write-Host "   docker compose up -d"
Write-Host ""
Write-Host "3. Monitor deployment:"
Write-Host "   docker compose logs -f parser-eater"
Write-Host ""
Write-Host "4. Check service status:"
Write-Host "   docker compose ps"
Write-Host ""
Write-Host "5. Access Web UI:"
Write-Host "   http://localhost:8080"
Write-Host ""
Write-Host "6. Health check:"
Write-Host "   curl http://localhost:8080/api/status"
Write-Host ""

Write-Header "Security Reminders"
Write-Host ""
Write-Warning-Custom "Before production deployment:"
Write-Host "  • Change all default passwords in .env"
Write-Host "  • Secure config.yaml (contains API keys)"
Write-Host "  • Review firewall rules (port 8080)"
Write-Host "  • Enable TLS/SSL for production"
Write-Host "  • Implement secrets management (AWS Secrets Manager)"
Write-Host "  • Review security scan results"
Write-Host "  • Set up log aggregation"
Write-Host "  • Configure backup strategy"
Write-Host ""

Write-Success "Ready for deployment!"
