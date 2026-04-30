"""Security utility functions for preventing common vulnerabilities."""

import secrets
import re
import socket
import unicodedata
import fnmatch
from typing import Optional, Sequence, Tuple
from urllib.parse import urlparse
import ipaddress
import logging

logger = logging.getLogger(__name__)


# W5 (plan 2026-04-29): default allowlist for the Observo SaaS control
# plane. Call sites for outbound Observo HTTP must pass this constant so
# only api.observo.ai-shaped hostnames are accepted.
OBSERVO_DEFAULT_ALLOWLIST: Tuple[str, ...] = ("*.observo.ai",)


def constant_time_compare(a: str, b: str) -> bool:
    """
    SECURITY FIX: Constant-time string comparison to prevent timing attacks.
    
    Uses secrets.compare_digest() which performs constant-time comparison
    to prevent timing-based side-channel attacks.
    
    Args:
        a: First string to compare
        b: Second string to compare
        
    Returns:
        True if strings are equal, False otherwise
    """
    return secrets.compare_digest(a, b)


def validate_uuid_format(value: str) -> bool:
    """
    SECURITY FIX: Validate that a string is a valid UUID format.
    
    Prevents template injection via request_id manipulation.
    
    Args:
        value: String to validate
        
    Returns:
        True if valid UUID format, False otherwise
    """
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(value))


def sanitize_request_id(request_id: str) -> str:
    """
    SECURITY FIX: Sanitize request ID to ensure it's safe for template rendering.
    
    Args:
        request_id: Request ID to sanitize
        
    Returns:
        Sanitized request ID (UUID format only)
    """
    if validate_uuid_format(request_id):
        return request_id
    # If invalid, generate a new secure UUID
    logger.warning(f"Invalid request ID format detected: {request_id[:50]}")
    return secrets.token_urlsafe(16)


def normalize_unicode(text: str) -> str:
    """
    SECURITY FIX: Normalize Unicode to prevent homoglyph attacks.
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text
    """
    # Normalize to NFC form and filter out non-ASCII if needed
    normalized = unicodedata.normalize('NFC', text)
    # For parser names, we want strict ASCII
    if not normalized.isascii():
        logger.warning(f"Non-ASCII characters detected in input: {text[:50]}")
    return normalized


def validate_parser_name(parser_name: str) -> Tuple[bool, Optional[str]]:
    """
    SECURITY FIX: Validate parser name format with Unicode normalization.
    
    Args:
        parser_name: Parser name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not parser_name:
        return False, "Parser name cannot be empty"
    
    # Normalize Unicode
    normalized = normalize_unicode(parser_name)
    
    # Check length
    if len(normalized) > 100:
        return False, "Parser name too long (max 100 characters)"
    
    if len(normalized) < 1:
        return False, "Parser name too short (min 1 character)"
    
    # Strict ASCII validation for parser names
    if not normalized.isascii():
        return False, "Parser name must contain only ASCII characters"
    
    # Check format: alphanumeric, underscore, hyphen only
    if not re.match(r'^[a-zA-Z0-9_-]+$', normalized):
        return False, "Parser name contains invalid characters (only a-z, A-Z, 0-9, _, - allowed)"
    
    return True, None


_IPAddress = "ipaddress.IPv4Address | ipaddress.IPv6Address"


def _is_disallowed_ip(ip) -> Optional[str]:
    """Return a rejection reason if ``ip`` falls in a disallowed range,
    else None. Centralizes the RFC1918 / loopback / link-local /
    reserved / multicast checks so direct-IP and resolved-IP paths use
    identical rules.

    Accepts the union of ``ipaddress.IPv4Address`` and
    ``ipaddress.IPv6Address`` (typed as bare ``Any`` to keep mypy happy
    without conditional-version typing gymnastics; the runtime calls
    are identical for both classes).
    """
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        return f"Private/loopback/link-local IP addresses are not allowed: {ip}"
    if ip.is_multicast or ip.is_reserved:
        return f"Reserved/multicast IP addresses are not allowed: {ip}"
    if ip.is_unspecified:
        return f"Unspecified IP addresses are not allowed: {ip}"
    return None


def validate_url_for_ssrf(
    url: str,
    allowed_hosts: Optional[list] = None,
    *,
    host_allowlist: Optional[Sequence[str]] = None,
) -> Tuple[bool, Optional[str]]:
    """SECURITY FIX: Validate URL to prevent SSRF attacks.

    Hardened (W5, plan 2026-04-29): in addition to the existing
    direct-IP-literal block, hostnames are now resolved via
    ``socket.getaddrinfo`` and every resolved IP is re-checked against
    the same private/loopback/link-local/reserved/multicast rules.
    A hostname like ``internal.example`` that resolves to ``10.0.0.5``
    is rejected.

    DNS-rebinding caveat: this helper validates the hostname's current
    DNS resolution at the moment of the call. A malicious authoritative
    DNS server can return a public IP at validate time and a private IP
    on the next ``getaddrinfo`` (the one the actual ``urlopen`` /
    ``aiohttp`` request issues). True defense-in-depth requires either
    (a) pinning the resolved IP and passing it directly to the HTTP
    client, or (b) running the outbound HTTP client behind a proxy that
    enforces the same allowlist. Treat this helper as a strong first
    line, not a complete fix.

    Args:
        url: URL to validate
        allowed_hosts: Legacy positional list of exact-match allowed
            hostnames (kept for backwards compatibility with existing
            call sites).
        host_allowlist: Wildcard-allowlist of permitted hostnames. Each
            entry is matched against ``parsed.hostname`` via
            ``fnmatch.fnmatchcase``. If provided, the URL must match at
            least one entry. Use the module-level
            ``OBSERVO_DEFAULT_ALLOWLIST`` for Observo SaaS calls.

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in ['http', 'https']:
            return False, f"Invalid URL scheme: {parsed.scheme}"

        hostname = parsed.hostname
        if not hostname:
            return False, "URL is missing a hostname"

        # 1) Direct IP-literal block (preserved behavior).
        is_ip_literal = False
        try:
            ip = ipaddress.ip_address(hostname)
            is_ip_literal = True
            reason = _is_disallowed_ip(ip)
            if reason:
                return False, reason
        except ValueError:
            # Not an IP address, falls through to the hostname path.
            pass

        # 2) Allowlist enforcement.
        # Wildcard allowlist (new, preferred) — IP literals always fail
        # an allowlist that contains hostname patterns; if you need to
        # allow a literal IP, pass it explicitly via legacy
        # ``allowed_hosts``.
        if host_allowlist:
            matched = any(
                fnmatch.fnmatchcase(hostname.lower(), pat.lower())
                for pat in host_allowlist
            )
            if not matched:
                return False, (
                    f"Hostname not in allowlist: {hostname} "
                    f"(allowlist={list(host_allowlist)})"
                )

        # Legacy exact-match list (pre-existing API).
        if allowed_hosts and hostname not in allowed_hosts:
            return False, f"Hostname not in allowed list: {hostname}"

        # 3) DNS resolution + per-IP recheck for hostnames.
        #
        # Skipped for IP literals (already rechecked above) and skipped
        # if getaddrinfo raises — DNS errors are handled by the caller's
        # outbound HTTP client; we don't want a flaky DNS lookup to
        # block a legitimate save. The allowlist gate above is the
        # primary defense against attacker-controlled hostnames.
        if not is_ip_literal:
            try:
                infos = socket.getaddrinfo(hostname, None)
            except (socket.gaierror, UnicodeError, OSError) as exc:
                logger.warning(
                    "validate_url_for_ssrf: DNS lookup failed for %s: %s",
                    hostname, exc,
                )
                return True, None

            for info in infos:
                # info shape: (family, type, proto, canonname, sockaddr)
                # sockaddr is (ip, port) for AF_INET, (ip, port, fl, sc)
                # for AF_INET6.
                try:
                    sockaddr = info[4]
                    resolved_ip_str = sockaddr[0]
                    resolved_ip = ipaddress.ip_address(resolved_ip_str)
                except (IndexError, ValueError, TypeError):
                    continue
                reason = _is_disallowed_ip(resolved_ip)
                if reason:
                    return False, (
                        f"Hostname {hostname} resolves to disallowed IP "
                        f"{resolved_ip}: {reason}"
                    )

        return True, None

    except Exception as e:
        logger.error(f"URL validation error: {e}")
        return False, f"Invalid URL format: {str(e)}"


def sanitize_log_input(text: str, max_length: int = 1000) -> str:
    """
    SECURITY FIX: Sanitize input for logging to prevent log injection.
    
    Args:
        text: Text to sanitize
        max_length: Maximum length for log entry
        
    Returns:
        Sanitized text safe for logging
    """
    if not text:
        return ""
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length] + "... [truncated]"
    
    # Remove newlines and control characters
    sanitized = re.sub(r'[\r\n\t]', ' ', text)
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
    
    return sanitized


def validate_json_depth(data: dict, max_depth: int = 10, current_depth: int = 0) -> Tuple[bool, Optional[str]]:
    """
    SECURITY FIX: Validate JSON nesting depth to prevent DoS attacks.
    
    Args:
        data: Dictionary to validate
        max_depth: Maximum allowed nesting depth
        current_depth: Current depth (internal use)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if current_depth > max_depth:
        return False, f"JSON nesting depth exceeds maximum ({max_depth} levels)"
    
    for value in data.values():
        if isinstance(value, dict):
            is_valid, error = validate_json_depth(value, max_depth, current_depth + 1)
            if not is_valid:
                return False, error
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    is_valid, error = validate_json_depth(item, max_depth, current_depth + 1)
                    if not is_valid:
                        return False, error
    
    return True, None


def get_secure_request_id() -> str:
    """
    SECURITY FIX: Generate cryptographically secure request ID.
    
    Uses secrets.token_urlsafe() instead of UUID for better entropy.
    
    Returns:
        Secure request ID string
    """
    return secrets.token_urlsafe(16)


def get_secure_nonce() -> str:
    """
    SECURITY FIX: Generate cryptographically secure CSP nonce.
    
    Returns:
        Secure nonce string
    """
    return secrets.token_urlsafe(16)

