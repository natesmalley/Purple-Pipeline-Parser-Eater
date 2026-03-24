#!/bin/bash
# Generate self-signed TLS certificates for development
# SECURITY: These are for DEVELOPMENT ONLY! Use proper CA certificates for production.

set -e

CERT_DIR="./certs"
DAYS_VALID=365

echo "=================================================="
echo "Generating Development TLS Certificates"
echo "=================================================="
echo ""

# Create certs directory
mkdir -p "$CERT_DIR"
echo "✓ Created directory: $CERT_DIR"

# Generate private key and certificate
echo ""
echo "Generating RSA 4096-bit private key and self-signed certificate..."
echo "(This may take a moment)"
echo ""

openssl req -x509 -newkey rsa:4096 \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt" \
  -days $DAYS_VALID -nodes \
  -subj "/CN=localhost/O=Purple Pipeline Parser Eater Dev/C=US" \
  -addext "subjectAltName=DNS:localhost,DNS:127.0.0.1,IP:127.0.0.1"

# Set appropriate permissions
chmod 600 "$CERT_DIR/server.key"
chmod 644 "$CERT_DIR/server.crt"

echo ""
echo "=================================================="
echo "✅ Development certificates generated successfully!"
echo "=================================================="
echo ""
echo "Certificate file: $CERT_DIR/server.crt"
echo "Private key file: $CERT_DIR/server.key"
echo "Valid for: $DAYS_VALID days"
echo ""
echo "⚠️  WARNING: These are SELF-SIGNED certificates!"
echo "   - For DEVELOPMENT use only"
echo "   - Browsers will show security warnings"
echo "   - NOT suitable for production"
echo ""
echo "For production:"
echo "   - Use Let's Encrypt (certbot)"
echo "   - Or obtain certificates from a trusted CA"
echo "   - Update config.yaml with production cert paths"
echo ""
echo "To use these certificates:"
echo "   1. Update config.yaml:"
echo "      web_ui:"
echo "        tls:"
echo "          enabled: true"
echo "          cert_file: \"./certs/server.crt\""
echo "          key_file: \"./certs/server.key\""
echo ""
echo "   2. Start the application"
echo ""
echo "   3. Access via: https://localhost:8443"
echo "      (Accept the security warning for self-signed cert)"
echo ""
echo "=================================================="
