"""
Gunicorn Production Configuration

This module provides production-ready Gunicorn configuration for the
Purple Pipeline Parser Eater web service.

Usage:
    gunicorn -c gunicorn_config.py wsgi_production:app

Configuration Features:
- Worker pool: sync workers for I/O-bound workloads
- Worker connections: 1000 (tuned for many concurrent requests)
- Timeout: 60 seconds (prevents hanging requests)
- Keep-alive: 5 seconds (HTTP keep-alive)
- Max requests: 1000 (worker recycling to prevent memory leaks)
- Access logging: Structured JSON format
- Security: Limited by systemd service file

Type hints:
    All configuration variables with type hints

Examples:
    # Basic production deployment
    gunicorn -c gunicorn_config.py wsgi_production:app

    # With SSL/TLS
    gunicorn -c gunicorn_config.py \\
             --certfile=/opt/certs/server.crt \\
             --keyfile=/opt/certs/server.key \\
             wsgi_production:app

    # Override workers
    gunicorn -c gunicorn_config.py -w 8 wsgi_production:app

    # Dry-run to test configuration
    gunicorn -c gunicorn_config.py --check-config wsgi_production:app
"""

import os
import logging
from pathlib import Path

# Base configuration
project_root = Path(__file__).parent
log_dir = project_root / "logs"

# Create logs directory if it doesn't exist
log_dir.mkdir(exist_ok=True, parents=True)

# ==============================================================================
# WORKER CONFIGURATION
# ==============================================================================

# Number of worker processes.
#
# Stream A6 — default to 1 (singleton-safe). Each worker constructs its own
# follower-mode StateStore that hot-reloads from the shared persisted JSON
# on every read, so multiple workers ARE safe — but the default is 1 so
# operators have to opt into multi-worker fan-out via GUNICORN_WORKERS.
workers = int(os.getenv('GUNICORN_WORKERS', 1))

# Worker class (sync for I/O-bound, gevent for concurrency)
worker_class = 'sync'

# Maximum number of pending connections to accept
backlog = 2048

# Number of concurrent connections per worker
worker_connections = 1000

# Timeout in seconds
timeout = 60

# Keep-alive timeout in seconds
keepalive = 5

# Maximum number of requests before worker is gracefully restarted
max_requests = 1000

# Add randomness to max_requests to prevent thundering herd
max_requests_jitter = 100

# ==============================================================================
# SOCKET CONFIGURATION
# ==============================================================================

# Bind addresses (can be overridden with -b flag)
bind = [
    'unix:/run/purple-parser-eater.sock',  # For reverse proxy
    '0.0.0.0:8080'                         # Direct access
]

# Socket backlog size
backlog = 2048

# ==============================================================================
# SERVER MECHANICS
# ==============================================================================

# Daemon mode (should be handled by systemd, not by Gunicorn)
daemon = False

# Process name in ps output
proc_name = 'purple-parser-eater'

# PID file (should be managed by systemd)
pidfile = None

# Change to this directory before loading the app
# Gunicorn will change to project root
chdir = str(project_root)

# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================

# Log level
loglevel = 'info'

# Access log format (JSON for structured logging)
access_log_format = (
    '{"timestamp": "%(t)s", '
    '"remote_addr": "%(h)s", '
    '"request_line": "%(r)s", '
    '"status_code": "%(s)s", '
    '"response_length": "%(b)s", '
    '"request_time": "%(D)s", '
    '"referer": "%(f)s", '
    '"user_agent": "%(a)s"}'
)

# Access log file path
# Use '-' for stdout (captured by systemd journal)
accesslog = '-'

# Error log file path
# Use '-' for stderr (captured by systemd journal)
errorlog = '-'

# Disable logging of request/response data
statsd_changes_only = True

# Use syslog for logging if available
# syslog = True
# syslog_addr = 'udp://localhost:514'
# syslog_facility = 'local6'
# syslog_prefix = 'purple-parser-eater'

# ==============================================================================
# SSL/TLS CONFIGURATION
# ==============================================================================

# Certificate and key files (can be overridden with command-line flags)
# These paths are relative to project root if not absolute
certfile = os.getenv('GUNICORN_CERTFILE', None)
keyfile = os.getenv('GUNICORN_KEYFILE', None)

# SSL version
ssl_version = 'TLSv1_2'

# Cipher suite (balanced security and performance)
ciphers = (
    'ECDHE-RSA-AES256-GCM-SHA384:'
    'ECDHE-RSA-AES128-GCM-SHA256:'
    'DHE-RSA-AES256-GCM-SHA384:'
    'DHE-RSA-AES128-GCM-SHA256'
)

# ==============================================================================
# REQUEST/RESPONSE CONFIGURATION
# ==============================================================================

# HTTP version to support
# 'auto' detects HTTP/1.1 or HTTP/1.0 based on client
http = 'auto'

# Limit allowed request header fields
limit_request_fields = 100

# Limit allowed request header size
limit_request_line = 8190

# ==============================================================================
# SECURITY CONFIGURATION
# ==============================================================================

# Prevent running as root
# (configured in systemd service file instead)
# def when_ready(server):
#     if os.getuid() == 0:
#         raise RuntimeError("Do not run Gunicorn as root!")

# Disable X-Forwarded-For header processing
# (configure in reverse proxy instead)
secure_scheme_headers = {
    'X-FORWARDED-PROTOCOL': 'ssl',
    'X-FORWARDED-PROTO': 'https',
    'X-FORWARDED-SSL': 'on',
}

# Trust X-Forwarded-For from configured proxies
# (configure only for trusted proxies)
forwarded_allow_ips = '127.0.0.1'

# ==============================================================================
# PERFORMANCE TUNING
# ==============================================================================

# Use sendfile() for static files (if applicable)
sendfile = True

# TCP_NODELAY socket option (disable Nagle's algorithm)
tcp_nodelay = True

# SO_REUSEADDR socket option
preload_app = False  # Set to True if using shared memory or thread pools

# ==============================================================================
# DEBUGGING & MONITORING
# ==============================================================================

# Enable debug mode (NEVER in production)
debug = False

# Print access logs to stdout
print_config = False

# ==============================================================================
# LIFECYCLE HOOKS
# ==============================================================================

def when_ready(server):
    """
    Called just after the server is started.
    Useful for pre-loading resources.
    """
    logging.getLogger('gunicorn.info').info(
        'Purple Pipeline Parser Eater server is ready'
    )


def on_starting(server):
    """Called just before the master process is initialized."""
    logging.getLogger('gunicorn.info').info('Starting server...')


def on_exit(server):
    """Called just before exiting Gunicorn."""
    logging.getLogger('gunicorn.info').info('Shutting down server...')


def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass


def post_fork(server, worker):
    """Called just after a worker has been forked.

    Stream A6 — DO NOT spawn the conversion / GitHub-sync / feedback /
    SDL-audit loops here. Those run in a separate compose service named
    ``parser-eater-worker`` (``continuous_conversion_service.py
    --worker-only``) which shares the ``app-data`` volume via
    ``STATE_STORE_PATH`` and the file-backed ``FeedbackChannel``. Spawning
    them inside a gunicorn worker would race the dedicated worker over
    the same StateStore and produce duplicate conversions.
    """
    pass


def pre_exec(server):
    """Called just before a new master process is exec()ed."""
    pass


def post_worker_int(worker):
    """Called just after a worker exited on SIGINT."""
    pass


def worker_int(worker):
    """Called when a worker received SIGINT or SIGQUIT signal."""
    pass


def worker_abort(worker):
    """Called when a worker is aborted due to timeout."""
    logging.getLogger('gunicorn.warning').warning(
        f'Worker {worker.pid} aborted due to timeout'
    )


def child_exit(server, worker):
    """Called just after a worker has been exited (in the master process)."""
    pass


# ==============================================================================
# EXAMPLE DEPLOYMENT COMMANDS
# ==============================================================================

"""
Production Deployment:

1. Generate SSL certificates:
   ./scripts/setup_tls_certificates.sh prod --domain example.com

2. Start with Gunicorn:
   gunicorn -c gunicorn_config.py \\
            --certfile=certs/server.crt \\
            --keyfile=certs/server.key \\
            wsgi_production:app

3. Or use systemd service (recommended):
   sudo systemctl start purple-parser-eater
   sudo systemctl enable purple-parser-eater

4. Monitor with Prometheus:
   curl http://localhost:9090/metrics

5. View dashboards in Grafana:
   http://localhost:3000/

Systemd Status:
   sudo systemctl status purple-parser-eater
   sudo journalctl -u purple-parser-eater -f

Configuration Validation:
   gunicorn -c gunicorn_config.py --check-config wsgi_production:app

Performance Testing:
   ab -n 10000 -c 100 https://localhost:8080/health
   wrk -t 4 -c 100 -d 30s https://localhost:8080/
"""
