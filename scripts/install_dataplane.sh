#!/bin/bash

################################################################################
# Dataplane Binary Installation Script
# Installs Observo dataplane binary to /opt/dataplane/ with architecture detection
# Usage: ./install_dataplane.sh [--force] [--binary-source /path/to/binary]
# Requirements: sudo, curl (optional for verification)
################################################################################

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DATAPLANE_DIR="/opt/dataplane"
DATAPLANE_BINARY_NAME="dataplane"
DATAPLANE_BINARY="${DATAPLANE_DIR}/${DATAPLANE_BINARY_NAME}"
DATAPLANE_USER="dataplane"
DATAPLANE_GROUP="dataplane"
BINARY_SOURCE=""
FORCE_INSTALL=false

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

################################################################################
# Function: Detect system architecture
################################################################################
detect_architecture() {
    local arch
    arch=$(uname -m)

    case "$arch" in
        x86_64|amd64)
            echo "amd64"
            ;;
        aarch64|arm64)
            echo "aarch64"
            ;;
        *)
            log_error "Unsupported architecture: $arch"
            exit 1
            ;;
    esac
}

################################################################################
# Function: Find dataplane binary source
################################################################################
find_binary_source() {
    local arch=$1
    local search_paths=(
        "./dataplane.${arch}"
        "./bin/dataplane.${arch}"
        "../dataplane.${arch}"
        "${HOME}/dataplane.${arch}"
    )

    if [[ -n "$BINARY_SOURCE" ]]; then
        if [[ ! -f "$BINARY_SOURCE" ]]; then
            log_error "Specified binary source not found: $BINARY_SOURCE"
            exit 1
        fi
        echo "$BINARY_SOURCE"
        return 0
    fi

    for path in "${search_paths[@]}"; do
        if [[ -f "$path" ]]; then
            log_info "Found dataplane binary at: $path"
            echo "$path"
            return 0
        fi
    done

    log_error "Dataplane binary not found for architecture: $arch"
    log_error "Searched paths:"
    for path in "${search_paths[@]}"; do
        log_error "  - $path"
    done
    log_error "Provide --binary-source /path/to/dataplane.<arch>"
    exit 1
}

################################################################################
# Function: Verify binary integrity
################################################################################
verify_binary() {
    local binary_path=$1

    log_info "Verifying binary integrity..."

    # Check if binary is executable
    if [[ ! -x "$binary_path" ]]; then
        log_warn "Binary is not executable, fixing permissions..."
        chmod +x "$binary_path"
    fi

    # Check if binary is ELF format
    if ! file "$binary_path" | grep -q "ELF"; then
        log_error "Binary is not a valid ELF executable"
        exit 1
    fi

    # Check binary size (should be >50MB)
    local size
    size=$(stat -f%z "$binary_path" 2>/dev/null || stat -c%s "$binary_path" 2>/dev/null)
    if [[ $size -lt 52428800 ]]; then
        log_warn "Binary size is small (${size} bytes), may be corrupted"
    fi

    log_success "Binary verification passed"
}

################################################################################
# Function: Check prerequisites
################################################################################
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if running as root or with sudo
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root or with sudo"
        log_error "Usage: sudo $0"
        exit 1
    fi

    # Check required commands
    for cmd in mkdir chmod chown; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "Required command not found: $cmd"
            exit 1
        fi
    done

    log_success "Prerequisites check passed"
}

################################################################################
# Function: Create dataplane user and group
################################################################################
setup_user() {
    log_info "Setting up dataplane user and group..."

    # Create group if it doesn't exist
    if ! getent group "$DATAPLANE_GROUP" > /dev/null; then
        log_info "Creating group: $DATAPLANE_GROUP"
        groupadd -r "$DATAPLANE_GROUP" 2>/dev/null || true
    fi

    # Create user if it doesn't exist
    if ! getent passwd "$DATAPLANE_USER" > /dev/null; then
        log_info "Creating user: $DATAPLANE_USER"
        useradd -r -g "$DATAPLANE_GROUP" -s /bin/false "$DATAPLANE_USER" 2>/dev/null || true
    fi

    log_success "User/group setup complete"
}

################################################################################
# Function: Create installation directory
################################################################################
setup_directory() {
    log_info "Setting up installation directory: $DATAPLANE_DIR"

    # Create directory
    if [[ ! -d "$DATAPLANE_DIR" ]]; then
        mkdir -p "$DATAPLANE_DIR"
        log_info "Created directory: $DATAPLANE_DIR"
    fi

    # Set permissions: readable/executable by owner and group, not world
    chmod 755 "$DATAPLANE_DIR"
    chown root:"$DATAPLANE_GROUP" "$DATAPLANE_DIR"

    log_success "Directory setup complete"
}

################################################################################
# Function: Backup existing binary
################################################################################
backup_existing() {
    if [[ -f "$DATAPLANE_BINARY" ]]; then
        local timestamp
        timestamp=$(date +%Y%m%d_%H%M%S)
        local backup_file="${DATAPLANE_BINARY}.backup.${timestamp}"

        log_warn "Existing binary found, creating backup: $backup_file"
        cp "$DATAPLANE_BINARY" "$backup_file"
        log_success "Backup created: $backup_file"
    fi
}

################################################################################
# Function: Install binary
################################################################################
install_binary() {
    local source_binary=$1

    log_info "Installing dataplane binary from: $source_binary"

    # Backup existing binary
    backup_existing

    # Copy binary
    cp "$source_binary" "$DATAPLANE_BINARY"
    log_info "Binary installed to: $DATAPLANE_BINARY"

    # Set permissions: readable/executable by owner and group, not world
    chmod 750 "$DATAPLANE_BINARY"
    chown root:"$DATAPLANE_GROUP" "$DATAPLANE_BINARY"

    log_success "Binary installation complete"
}

################################################################################
# Function: Verify installation
################################################################################
verify_installation() {
    log_info "Verifying installation..."

    # Check if binary exists
    if [[ ! -f "$DATAPLANE_BINARY" ]]; then
        log_error "Installation verification failed: binary not found"
        exit 1
    fi

    # Check if binary is executable
    if [[ ! -x "$DATAPLANE_BINARY" ]]; then
        log_error "Installation verification failed: binary is not executable"
        exit 1
    fi

    # Display installation summary
    echo ""
    log_info "Installation Summary:"
    echo -e "  Binary path:     ${GREEN}${DATAPLANE_BINARY}${NC}"
    echo -e "  Owner:           ${GREEN}root:${DATAPLANE_GROUP}${NC}"
    echo -e "  Permissions:     ${GREEN}750${NC}"
    echo ""

    log_success "Installation verification passed"
}

################################################################################
# Function: Create systemd service file (optional)
################################################################################
create_systemd_service() {
    if [[ ! -f /etc/systemd/system/dataplane.service ]]; then
        log_info "Creating systemd service file..."
        cat > /etc/systemd/system/dataplane.service << 'EOF'
[Unit]
Description=Observo Dataplane Binary Manager
Documentation=https://observo.ai/docs
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=dataplane
Group=dataplane
ExecStart=/opt/dataplane/dataplane
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
Environment="LD_LIBRARY_PATH=/opt/dataplane/lib"

[Install]
WantedBy=multi-user.target
EOF
        chmod 644 /etc/systemd/system/dataplane.service
        systemctl daemon-reload 2>/dev/null || true
        log_success "Systemd service file created"
    fi
}

################################################################################
# Function: Parse command line arguments
################################################################################
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force)
                FORCE_INSTALL=true
                shift
                ;;
            --binary-source)
                BINARY_SOURCE="$2"
                shift 2
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

################################################################################
# Function: Show help
################################################################################
show_help() {
    cat << EOF
Dataplane Binary Installation Script

Usage: $0 [OPTIONS]

Options:
    --force              Force installation even if binary already exists
    --binary-source PATH Path to dataplane binary (auto-detected if not specified)
    --help              Show this help message

Examples:
    sudo $0
    sudo $0 --binary-source ./dataplane.amd64
    sudo $0 --force

Description:
    Installs Observo dataplane binary to /opt/dataplane/ with the following:
    - Architecture auto-detection (amd64/aarch64)
    - Binary verification
    - User/group creation
    - Systemd service file (optional)
    - Backup of existing binary

Requirements:
    - Linux operating system
    - Root or sudo access
    - Dataplane binary available (locally or specified)

Installation Directory:
    /opt/dataplane/dataplane

Service File (optional):
    /etc/systemd/system/dataplane.service

User/Group:
    dataplane:dataplane (created if not exists)

EOF
}

################################################################################
# Main execution
################################################################################
main() {
    echo ""
    log_info "Starting Dataplane Binary Installation"
    echo ""

    # Parse arguments
    parse_args "$@"

    # Detect architecture
    local arch
    arch=$(detect_architecture)
    log_info "Detected architecture: $arch"

    # Check prerequisites
    check_prerequisites

    # Check if already installed
    if [[ -f "$DATAPLANE_BINARY" ]] && [[ "$FORCE_INSTALL" == false ]]; then
        log_warn "Dataplane binary already installed at: $DATAPLANE_BINARY"
        log_warn "Use --force to reinstall"
        exit 0
    fi

    # Find binary source
    local source_binary
    source_binary=$(find_binary_source "$arch")

    # Verify source binary
    verify_binary "$source_binary"

    # Setup user and group
    setup_user

    # Setup directory
    setup_directory

    # Install binary
    install_binary "$source_binary"

    # Create systemd service (optional)
    if command -v systemctl &> /dev/null; then
        create_systemd_service
    fi

    # Verify installation
    verify_installation

    echo ""
    log_success "Dataplane installation completed successfully!"
    echo ""
}

# Run main function
main "$@"
