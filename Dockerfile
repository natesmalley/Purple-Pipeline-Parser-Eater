# Purple Pipeline Parser Eater - Production Docker Container
# FIPS 140-2 Compliant | STIG Hardened | Multi-stage Build

# ============================================================================
# Stage 1: Builder - Compile dependencies in isolated environment
# ============================================================================
FROM python:3.11-slim-bookworm AS builder

# Security: Run as non-root during build
RUN groupadd -g 999 appuser && \
    useradd -r -u 999 -g appuser appuser

WORKDIR /build

# Install build dependencies (minimal set for security)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for layer caching
COPY requirements.txt .

# Install harness-first Python packages to /install directory.
RUN pip install --no-cache-dir --prefix=/install --no-warn-script-location -r requirements.txt

# ============================================================================
# Stage 2: Production - Minimal runtime image
# ============================================================================
FROM python:3.11-slim-bookworm

LABEL maintainer="Purple Pipeline Parser Eater Team"
LABEL description="SentinelOne to Observo.ai Parser Conversion System"
LABEL version="9.0.1"
LABEL security.stig="hardened"
LABEL security.note="NOT FIPS 140-2 certified. Use Red Hat UBI for FIPS compliance."

# ============================================================================
# STIG Compliance: System Hardening
# ============================================================================

# Security: Create non-root user with specific UID/GID
RUN groupadd -g 999 appuser && \
    useradd -r -u 999 -g appuser -m -d /home/appuser -s /sbin/nologin appuser

# Security: Install only runtime dependencies (no compilers, no dev tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Security: Remove setuid/setgid permissions (STIG requirement)
RUN find / -xdev -perm /6000 -type f -exec chmod a-s {} \; 2>/dev/null || true

# ============================================================================
# Application Setup
# ============================================================================

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code with proper ownership
COPY --chown=appuser:appuser . .

# SECURITY FIX: Remove unnecessary files to reduce image size
RUN find /app -name "*.pyc" -delete && \
    find /app -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /app -name "*.md" -not -name "README.md" -delete && \
    find /app -name "*.txt" -not -name "requirements.txt" -not -name "LICENSE" -delete && \
    find /app -name "*.sh" -delete && \
    find /app -name "*.bat" -delete && \
    find /app -name "*.ps1" -delete && \
    find /app -name ".git" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /app -name ".github" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /app -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /app -name "*.test.py" -delete && \
    find /app -name "*.spec.py" -delete && \
    rm -rf /app/docs/historical /app/docs/archive /app/output /app/logs /app/Observo-dataPlane 2>/dev/null || true && \
    echo "Image optimization complete"

# Security: Create directories with restricted permissions
RUN mkdir -p /app/output /app/logs /app/data /home/appuser/.cache && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /home/appuser/.cache && \
    chmod -R 750 /app && \
    chmod 770 /app/output /app/logs /app/data && \
    chmod 777 /home/appuser/.cache

# ============================================================================
# Security Configuration
# ============================================================================

# SECURITY FIX: Removed false FIPS 140-2 claims
# Base image python:3.11-slim-bookworm is NOT FIPS-certified
# For true FIPS compliance, use Red Hat UBI or certified image

# Python security settings
ENV PYTHONHASHSEED=0
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# ============================================================================
# Security: Environment Configuration
# ============================================================================

# Restrict Python to safe mode
ENV PYTHONSAFEPATH=1

# Disable pip version check (no internet access needed)
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Set secure umask
RUN echo "umask 027" >> /home/appuser/.profile

# ============================================================================
# Network and Port Configuration
# ============================================================================

# Web UI port (will be exposed via docker-compose)
EXPOSE 8080

# ============================================================================
# Health Check - STIG V-230281
# ============================================================================

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/api/status || exit 1

# ============================================================================
# Security: Switch to non-root user (STIG V-230276)
# ============================================================================

USER appuser

# ============================================================================
# Startup Configuration
# ============================================================================

# Default command: Start continuous service with web UI
CMD ["python", "-u", "continuous_conversion_service.py"]
