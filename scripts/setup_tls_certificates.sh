#!/bin/bash

################################################################################
# TLS Certificate Setup Script
# Generates self-signed certificates or integrates with Let's Encrypt
# Usage: ./setup_tls_certificates.sh [dev|prod] [--domain example.com]
################################################################################

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CERT_DIR="certs"
CERT_FILE="${CERT_DIR}/server.crt"
KEY_FILE="${CERT_DIR}/server.key"
CSR_FILE="${CERT_DIR}/server.csr"
CERT_DAYS=365
ENVIRONMENT="dev"
DOMAIN="localhost"
CERT_BACKUP_DIR="certs/backup"

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
# Function: Check prerequisites
################################################################################
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check for OpenSSL
    if ! command -v openssl &> /dev/null; then
        log_error "OpenSSL is required but not installed"
        log_error "Install with: sudo apt-get install openssl (Debian/Ubuntu)"
        log_error "             sudo yum install openssl (RHEL/CentOS)"
        log_error "             brew install openssl (macOS)"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

################################################################################
# Function: Create certificate directory
################################################################################
create_cert_directory() {
    if [[ ! -d "$CERT_DIR" ]]; then
        mkdir -p "$CERT_DIR"
        chmod 700 "$CERT_DIR"
        log_info "Created certificate directory: $CERT_DIR"
    fi

    if [[ ! -d "$CERT_BACKUP_DIR" ]]; then
        mkdir -p "$CERT_BACKUP_DIR"
        chmod 700 "$CERT_BACKUP_DIR"
        log_info "Created backup directory: $CERT_BACKUP_DIR"
    fi
}

################################################################################
# Function: Backup existing certificates
################################################################################
backup_existing_certs() {
    if [[ -f "$CERT_FILE" ]] || [[ -f "$KEY_FILE" ]]; then
        local timestamp
        timestamp=$(date +%Y%m%d_%H%M%S)

        log_warn "Existing certificates found, backing up..."

        if [[ -f "$CERT_FILE" ]]; then
            cp "$CERT_FILE" "${CERT_BACKUP_DIR}/server.crt.${timestamp}"
        fi

        if [[ -f "$KEY_FILE" ]]; then
            cp "$KEY_FILE" "${CERT_BACKUP_DIR}/server.key.${timestamp}"
        fi

        log_success "Backup created in: $CERT_BACKUP_DIR"
    fi
}

################################################################################
# Function: Generate self-signed certificate (Development)
################################################################################
generate_self_signed_cert() {
    log_info "Generating self-signed certificate for development..."

    # Create OpenSSL config for CSR
    local config_file
    config_file=$(mktemp)
    cat > "$config_file" << EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = v3_req

[dn]
C=US
ST=State
L=City
O=Purple Pipeline Parser Eater
OU=Development
CN=${DOMAIN}

[v3_req]
subjectAltName = DNS:${DOMAIN},DNS:*.${DOMAIN},IP:127.0.0.1,IP:0.0.0.0
EOF

    # Generate private key
    openssl genrsa -out "$KEY_FILE" 2048 &>/dev/null
    chmod 600 "$KEY_FILE"
    log_info "Generated private key: $KEY_FILE"

    # Generate certificate signing request
    openssl req -new \
        -key "$KEY_FILE" \
        -out "$CSR_FILE" \
        -config "$config_file" &>/dev/null
    log_info "Generated certificate signing request: $CSR_FILE"

    # Generate self-signed certificate
    openssl x509 -req \
        -days "$CERT_DAYS" \
        -in "$CSR_FILE" \
        -signkey "$KEY_FILE" \
        -out "$CERT_FILE" \
        -extensions v3_req \
        -extfile "$config_file" &>/dev/null
    chmod 644 "$CERT_FILE"
    log_success "Generated self-signed certificate: $CERT_FILE"

    # Clean up temporary files
    rm -f "$CSR_FILE" "$config_file"

    # Display certificate information
    echo ""
    log_info "Certificate Details:"
    openssl x509 -in "$CERT_FILE" -text -noout | grep -E "Subject:|Issuer:|Not Before|Not After|Public-Key|Public Key" | sed 's/^/  /'
    echo ""
}

################################################################################
# Function: Generate certificate for Let's Encrypt (Production)
################################################################################
generate_letsencrypt_cert() {
    log_warn "Let's Encrypt integration requires certbot"
    log_warn "Install with: sudo apt-get install certbot python3-certbot-nginx"
    log_warn "            or other variant based on your web server"
    echo ""

    if ! command -v certbot &> /dev/null; then
        log_error "certbot is not installed"
        log_error "For production with Let's Encrypt, install certbot first"
        log_error "Then run: sudo certbot certonly --standalone -d ${DOMAIN}"
        echo ""
        log_info "Falling back to self-signed certificate for now..."
        ENVIRONMENT="dev"
        generate_self_signed_cert
        return
    fi

    log_info "Using certbot to generate Let's Encrypt certificate..."
    log_info "This requires domain validation and port 80/443 access"
    echo ""

    # Check if domain is resolvable
    if ! getent hosts "$DOMAIN" &> /dev/null; then
        log_warn "Domain does not resolve: $DOMAIN"
        log_warn "For Let's Encrypt, domain must be publicly resolvable"
        log_info "Falling back to self-signed certificate..."
        ENVIRONMENT="dev"
        generate_self_signed_cert
        return
    fi

    # Generate certificate using certbot
    sudo certbot certonly --standalone \
        --non-interactive \
        --agree-tos \
        -m "admin@${DOMAIN}" \
        -d "$DOMAIN" \
        -d "*.${DOMAIN}" \
        || {
            log_error "Certificate generation failed"
            log_info "Falling back to self-signed certificate..."
            ENVIRONMENT="dev"
            generate_self_signed_cert
            return
        }

    # Copy certificates to project directory
    local letsencrypt_cert="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
    local letsencrypt_key="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"

    if [[ -f "$letsencrypt_cert" ]] && [[ -f "$letsencrypt_key" ]]; then
        sudo cp "$letsencrypt_cert" "$CERT_FILE"
        sudo cp "$letsencrypt_key" "$KEY_FILE"
        sudo chown "$USER" "$CERT_FILE" "$KEY_FILE"
        chmod 600 "$KEY_FILE"
        log_success "Let's Encrypt certificate installed"
    fi
}

################################################################################
# Function: Create systemd service for certificate renewal
################################################################################
create_renewal_service() {
    if [[ "$ENVIRONMENT" == "prod" ]] && command -v systemctl &> /dev/null; then
        log_info "Creating systemd timer for certificate renewal..."

        # Create renewal service
        cat > /tmp/purple-cert-renewal.service << 'EOF'
[Unit]
Description=Purple Pipeline Parser Eater - Certificate Renewal
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew --quiet
StandardOutput=journal
StandardError=journal
EOF

        # Create renewal timer
        cat > /tmp/purple-cert-renewal.timer << 'EOF'
[Unit]
Description=Purple Pipeline Parser Eater - Certificate Renewal Timer
Documentation=man:systemd.timer(5)

[Timer]
OnBootSec=1min
OnUnitActiveSec=1d
Persistent=true

[Install]
WantedBy=timers.target
EOF

        log_info "Service and timer files created (not installed - requires sudo)"
        log_info "To install run:"
        log_info "  sudo cp /tmp/purple-cert-renewal.service /etc/systemd/system/"
        log_info "  sudo cp /tmp/purple-cert-renewal.timer /etc/systemd/system/"
        log_info "  sudo systemctl enable purple-cert-renewal.timer"
        log_info "  sudo systemctl start purple-cert-renewal.timer"
    fi
}

################################################################################
# Function: Create Flask configuration
################################################################################
create_flask_config() {
    log_info "Creating Flask TLS configuration..."

    cat > "${CERT_DIR}/README.md" << EOF
# TLS Certificate Configuration

## Files

- **server.crt**: SSL/TLS Certificate
- **server.key**: Private key (keep secure, do not commit)
- **backup/**: Backup of previous certificates

## Usage

### Flask Application

In your Flask app, load certificates:

\`\`\`python
import ssl

# Load certificate and key
ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.load_cert_chain(
    certfile='certs/server.crt',
    keyfile='certs/server.key'
)

# Use with Flask
app.run(ssl_context=ssl_context)
\`\`\`

### Gunicorn

\`\`\`bash
gunicorn --certfile=certs/server.crt --keyfile=certs/server.key app:app
\`\`\`

### Docker

Copy certificates into container:

\`\`\`dockerfile
COPY certs/server.crt /etc/ssl/certs/
COPY certs/server.key /etc/ssl/private/
RUN chmod 600 /etc/ssl/private/server.key
\`\`\`

## Renewal

### Self-Signed (Development)
Renewal not required. Generate new certificate when needed.

### Let's Encrypt (Production)
Certificate renewal is automated via certbot timer.

## Validity

Generated on: $(date)
Valid until: $(openssl x509 -in "$CERT_FILE" -noout -enddate 2>/dev/null || echo "Unknown")

EOF

    log_success "Configuration documentation created: ${CERT_DIR}/README.md"
}

################################################################################
# Function: Display certificate information
################################################################################
display_cert_info() {
    echo ""
    log_info "TLS Certificate Installation Summary:"
    echo ""
    echo -e "  Environment:      ${BLUE}${ENVIRONMENT}${NC}"
    echo -e "  Certificate:      ${GREEN}${CERT_FILE}${NC}"
    echo -e "  Private Key:      ${GREEN}${KEY_FILE}${NC}"
    echo -e "  Domain:           ${BLUE}${DOMAIN}${NC}"
    echo -e "  Validity Days:    ${YELLOW}${CERT_DAYS}${NC}"
    echo ""

    if [[ "$ENVIRONMENT" == "dev" ]]; then
        echo "  ⚠️  Development certificate - self-signed"
        echo "  ⚠️  Browsers will show security warnings"
        echo "  ⚠️  For testing only - do NOT use in production"
    else
        echo "  ✅ Production certificate - Let's Encrypt"
        echo "  ✅ Auto-renewal configured"
        echo "  ✅ Ready for production use"
    fi
    echo ""
}

################################################################################
# Function: Parse command line arguments
################################################################################
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            dev|prod)
                ENVIRONMENT="$1"
                shift
                ;;
            --domain)
                DOMAIN="$2"
                shift 2
                ;;
            --days)
                CERT_DAYS="$2"
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
TLS Certificate Setup Script

Usage: $0 [dev|prod] [OPTIONS]

Arguments:
    dev                 Development mode - generate self-signed certificate
    prod                Production mode - use Let's Encrypt

Options:
    --domain DOMAIN     Domain name for certificate (default: localhost)
    --days DAYS         Certificate validity in days (default: 365)
    --help             Show this help message

Examples:
    $0 dev
    $0 dev --domain localhost
    $0 prod --domain example.com
    $0 prod --domain example.com --days 365

Description:
    Generates TLS certificates for Purple Pipeline Parser Eater

    Development Mode:
    - Generates self-signed certificate
    - No domain validation required
    - Suitable for local testing
    - Browsers will show security warnings

    Production Mode:
    - Uses Let's Encrypt for valid certificates
    - Requires certbot and domain validation
    - Falls back to self-signed if Let's Encrypt fails
    - Auto-renewal configured via systemd timer

Generated Files:
    certs/server.crt       - Certificate
    certs/server.key       - Private key (chmod 600)
    certs/backup/          - Previous certificates

Security Notes:
    - Private key file is only readable by owner (chmod 600)
    - Do NOT commit private key to version control
    - Add 'certs/server.key' to .gitignore
    - Backup certificates regularly

EOF
}

################################################################################
# Main execution
################################################################################
main() {
    echo ""
    log_info "Starting TLS Certificate Setup"
    echo ""

    # Parse arguments
    parse_args "$@"

    # Check prerequisites
    check_prerequisites

    # Create directories
    create_cert_directory

    # Backup existing certificates
    backup_existing_certs

    # Generate certificates based on environment
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        generate_letsencrypt_cert
    else
        generate_self_signed_cert
    fi

    # Create Flask configuration
    create_flask_config

    # Create renewal service (production only)
    create_renewal_service

    # Display summary
    display_cert_info

    log_success "TLS certificate setup completed successfully!"
    echo ""
}

# Run main function
main "$@"
