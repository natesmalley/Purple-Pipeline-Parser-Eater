"""Security utility functions for preventing common vulnerabilities."""

import secrets
import re
import unicodedata
from typing import Optional, Tuple
from urllib.parse import urlparse
import ipaddress
import logging

logger = logging.getLogger(__name__)


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


def validate_url_for_ssrf(url: str, allowed_hosts: Optional[list] = None) -> Tuple[bool, Optional[str]]:
    """
    SECURITY FIX: Validate URL to prevent SSRF attacks.
    
    Args:
        url: URL to validate
        allowed_hosts: Optional list of allowed hostnames
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        parsed = urlparse(url)
        
        # Check scheme
        if parsed.scheme not in ['http', 'https']:
            return False, f"Invalid URL scheme: {parsed.scheme}"
        
        # Check for private IP ranges
        if parsed.hostname:
            try:
                ip = ipaddress.ip_address(parsed.hostname)
                # Block private IP ranges
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    return False, f"Private IP addresses are not allowed: {parsed.hostname}"
                # Block multicast and reserved
                if ip.is_multicast or ip.is_reserved:
                    return False, f"Reserved IP addresses are not allowed: {parsed.hostname}"
            except ValueError:
                # Not an IP address, check hostname
                pass
            
            # Check against allowed hosts whitelist
            if allowed_hosts:
                if parsed.hostname not in allowed_hosts:
                    return False, f"Hostname not in allowed list: {parsed.hostname}"
        
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

