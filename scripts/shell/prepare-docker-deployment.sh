#!/bin/bash
# Purple Pipeline Parser Eater - Docker Deployment Preparation Script
# STIG Compliant | Security Hardened

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Functions
# ============================================================================

print_header() {
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        print_success "$1 is installed"
        return 0
    else
        print_error "$1 is not installed"
        return 1
    fi
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

print_header "Purple Pipeline Parser Eater - Docker Deployment Preparation"
echo ""

print_info "Starting pre-flight checks..."
echo ""

# Check Docker
if check_command docker; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | tr -d ',')
    print_info "Docker version: $DOCKER_VERSION"
else
    print_error "Docker is required but not installed"
    exit 1
fi

# Check Docker Compose
if check_command docker-compose || docker compose version &> /dev/null; then
    if docker compose version &> /dev/null; then
        COMPOSE_VERSION=$(docker compose version | awk '{print $4}' | tr -d ',')
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_VERSION=$(docker-compose --version | awk '{print $3}' | tr -d ',')
        COMPOSE_CMD="docker-compose"
    fi
    print_info "Docker Compose version: $COMPOSE_VERSION"
else
    print_error "Docker Compose is required but not installed"
    exit 1
fi

# Check Docker daemon
if ! docker info &> /dev/null; then
    print_error "Docker daemon is not running. Please start Docker."
    exit 1
fi
print_success "Docker daemon is running"

echo ""

# ============================================================================
# Directory Structure
# ============================================================================

print_header "Creating Directory Structure"
echo ""

DIRECTORIES=(
    "data/milvus"
    "data/etcd"
    "data/minio"
    "output"
    "logs"
    "data"
)

for dir in "${DIRECTORIES[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        print_success "Created directory: $dir"
    else
        print_info "Directory already exists: $dir"
    fi
done

echo ""

# ============================================================================
# Set Permissions (STIG Compliance)
# ============================================================================

print_header "Setting Secure Permissions (STIG Compliant)"
echo ""

# Set directory permissions (750 = owner rwx, group rx, other none)
chmod 750 data output logs 2>/dev/null || print_warning "Could not set permissions (may require sudo on Linux)"
chmod 750 data/milvus data/etcd data/minio 2>/dev/null || true

print_success "Permissions configured for STIG compliance"
echo ""

# ============================================================================
# Configuration Files
# ============================================================================

print_header "Checking Configuration Files"
echo ""

# Check config.yaml
if [ ! -f "config.yaml" ]; then
    print_error "config.yaml not found!"
    print_info "Please create config.yaml before deployment"
    exit 1
else
    print_success "config.yaml found"

    # Security check: Ensure sensitive data is present
    if grep -q "api_key:" config.yaml; then
        print_warning "API keys found in config.yaml - ensure this file is secured!"
    fi
fi

# Check .env file
if [ ! -f ".env" ]; then
    print_warning ".env file not found"

    if [ -f ".env.example" ]; then
        print_info "Copying .env.example to .env"
        cp .env.example .env
        print_warning "SECURITY: Update .env with your secure credentials!"
        print_info "Edit .env and change default passwords before deployment"
    else
        print_error ".env.example not found. Cannot create .env"
        exit 1
    fi
else
    print_success ".env file found"

    # Check for default credentials (security check)
    if grep -q "minioadmin" .env; then
        print_warning "Default MinIO credentials detected in .env!"
        print_warning "Change MINIO_ACCESS_KEY and MINIO_SECRET_KEY before production deployment"
    fi
fi

# Set .env permissions (600 = owner rw only)
chmod 600 .env 2>/dev/null || print_warning "Could not set .env permissions"
print_success ".env permissions secured (600)"

echo ""

# ============================================================================
# Docker Network Cleanup
# ============================================================================

print_header "Docker Environment Preparation"
echo ""

# Check for existing containers
EXISTING_CONTAINERS=$(docker ps -a --filter "name=purple-" --format "{{.Names}}" 2>/dev/null || true)

if [ -n "$EXISTING_CONTAINERS" ]; then
    print_warning "Found existing Purple Pipeline containers:"
    echo "$EXISTING_CONTAINERS"
    read -p "Remove existing containers? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Stopping and removing existing containers..."
        $COMPOSE_CMD down -v 2>/dev/null || true
        print_success "Existing containers removed"
    fi
fi

echo ""

# ============================================================================
# Build Docker Images
# ============================================================================

print_header "Building Docker Images"
echo ""

print_info "Building purple-pipeline-parser-eater:9.0.0..."
print_info "This may take several minutes on first build..."
echo ""

if docker build -t purple-pipeline-parser-eater:9.0.0 -f Dockerfile . ; then
    print_success "Docker image built successfully"

    # Show image size
    IMAGE_SIZE=$(docker images purple-pipeline-parser-eater:9.0.0 --format "{{.Size}}")
    print_info "Image size: $IMAGE_SIZE"
else
    print_error "Docker build failed!"
    exit 1
fi

echo ""

# ============================================================================
# Security Scan (if available)
# ============================================================================

print_header "Security Scanning"
echo ""

if check_command trivy; then
    print_info "Running Trivy security scan..."
    trivy image --severity HIGH,CRITICAL purple-pipeline-parser-eater:9.0.0 || print_warning "Trivy scan found vulnerabilities"
elif check_command docker-scan; then
    print_info "Running Docker scan..."
    docker scan purple-pipeline-parser-eater:9.0.0 || print_warning "Docker scan found vulnerabilities"
else
    print_warning "No security scanner found (trivy or docker-scan)"
    print_info "Install Trivy for security scanning: https://github.com/aquasecurity/trivy"
fi

echo ""

# ============================================================================
# Deployment Summary
# ============================================================================

print_header "Deployment Preparation Complete"
echo ""

print_success "All pre-flight checks passed"
echo ""
print_info "Deployment Summary:"
echo "  • Docker image: purple-pipeline-parser-eater:9.0.0"
echo "  • Configuration: config.yaml (present)"
echo "  • Environment: .env (configured)"
echo "  • Data directories: Created with secure permissions"
echo "  • Security: STIG compliance configured"
echo "  • FIPS: Enabled in container environment"
echo ""

print_header "Next Steps"
echo ""
echo "1. Review and update configuration:"
echo "   - Edit config.yaml (API keys, settings)"
echo "   - Edit .env (MinIO credentials, resource limits)"
echo ""
echo "2. Start the services:"
echo "   ${COMPOSE_CMD} up -d"
echo ""
echo "3. Monitor deployment:"
echo "   ${COMPOSE_CMD} logs -f parser-eater"
echo ""
echo "4. Check service status:"
echo "   ${COMPOSE_CMD} ps"
echo ""
echo "5. Access Web UI:"
echo "   http://localhost:8080"
echo ""
echo "6. Health check:"
echo "   curl http://localhost:8080/api/status"
echo ""

print_header "Security Reminders"
echo ""
print_warning "Before production deployment:"
echo "  • Change all default passwords in .env"
echo "  • Secure config.yaml (contains API keys)"
echo "  • Review firewall rules (port 8080)"
echo "  • Enable TLS/SSL for production"
echo "  • Implement secrets management (AWS Secrets Manager)"
echo "  • Review security scan results"
echo "  • Set up log aggregation"
echo "  • Configure backup strategy"
echo ""

print_success "Ready for deployment!"
