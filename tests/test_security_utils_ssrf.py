"""W5 (plan 2026-04-29): regression tests for `validate_url_for_ssrf`.

Hardened helper now does:
  * direct-IP-literal block (RFC1918, loopback, link-local, reserved,
    multicast),
  * `socket.getaddrinfo`-driven hostname resolution + per-IP recheck,
  * `host_allowlist` wildcard match (`*.observo.ai`).

These tests must NEVER perform a real DNS call; `socket.getaddrinfo` is
monkeypatched in every case that exercises the resolution path.
"""
from __future__ import annotations

import socket

import pytest

from utils.security_utils import (
    OBSERVO_DEFAULT_ALLOWLIST,
    validate_url_for_ssrf,
)


# A safe stub the helper accepts: returns one (family, type, proto,
# canonname, sockaddr) tuple where sockaddr[0] is the desired IP.
def _make_getaddrinfo(ip: str):
    def _stub(*_args, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]
    return _stub


# ---------------------------------------------------------------------------
# IP-literal blocklist: each direct-IP case rejects without DNS.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "http://10.0.0.1/",            # RFC1918
        "http://192.168.1.1/",         # RFC1918
        "http://172.16.0.5/",          # RFC1918
        "http://127.0.0.1/",           # loopback
        "http://127.0.0.1:8080/x",     # loopback w/ port + path
        "http://169.254.169.254/",     # AWS link-local IMDS
        "http://0.0.0.0/",             # unspecified (treated as reserved)
        "http://[::1]/",               # IPv6 loopback
        "http://[fe80::1]/",           # IPv6 link-local
        "http://224.0.0.1/",           # multicast
    ],
)
def test_ip_literal_blocked(url, monkeypatch):
    """Direct IP literals in the disallowed ranges are rejected without
    any DNS call."""
    def _fail_dns(*_a, **_kw):
        raise AssertionError(
            "getaddrinfo must NOT be called for an IP literal "
            f"(url={url!r})"
        )
    monkeypatch.setattr("socket.getaddrinfo", _fail_dns)

    ok, reason = validate_url_for_ssrf(url)
    assert ok is False, f"expected reject for {url!r}; got accept"
    assert reason
    assert isinstance(reason, str)


def test_public_ip_literal_accepted(monkeypatch):
    """A public IP literal (1.1.1.1) is allowed when no allowlist is set."""
    def _fail_dns(*_a, **_kw):
        raise AssertionError("getaddrinfo must NOT be called for an IP literal")
    monkeypatch.setattr("socket.getaddrinfo", _fail_dns)

    ok, reason = validate_url_for_ssrf("https://1.1.1.1/")
    assert ok is True, f"expected accept; reason={reason}"


# ---------------------------------------------------------------------------
# Hostname → resolved-IP recheck.
# ---------------------------------------------------------------------------

def test_hostname_resolves_to_loopback_rejected(monkeypatch):
    """A hostname that resolves to 127.0.0.1 must be rejected via the
    DNS recheck path."""
    monkeypatch.setattr("socket.getaddrinfo", _make_getaddrinfo("127.0.0.1"))

    ok, reason = validate_url_for_ssrf("https://internal.example/")
    assert ok is False
    assert reason and "127.0.0.1" in reason


def test_hostname_resolves_to_rfc1918_rejected(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", _make_getaddrinfo("10.0.0.5"))

    ok, reason = validate_url_for_ssrf("https://corp.internal/")
    assert ok is False
    assert reason and "10.0.0.5" in reason


def test_hostname_resolves_to_imds_rejected(monkeypatch):
    """169.254.169.254 (cloud metadata) is the canonical SSRF target."""
    monkeypatch.setattr(
        "socket.getaddrinfo", _make_getaddrinfo("169.254.169.254")
    )

    ok, reason = validate_url_for_ssrf("https://metadata.example/")
    assert ok is False
    assert reason and "169.254.169.254" in reason


def test_hostname_resolves_to_public_ip_accepted(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", _make_getaddrinfo("8.8.8.8"))

    ok, reason = validate_url_for_ssrf("https://example.com/")
    assert ok is True, f"expected accept; reason={reason}"


def test_hostname_dns_failure_does_not_block(monkeypatch):
    """When DNS lookup raises, we let the request proceed; the outbound
    HTTP client will surface the DNS error. The allowlist gate is the
    primary attacker-controlled-hostname defense."""
    def _gai_fail(*_a, **_kw):
        raise socket.gaierror("Name or service not known")
    monkeypatch.setattr("socket.getaddrinfo", _gai_fail)

    ok, _reason = validate_url_for_ssrf("https://does-not-resolve.example/")
    assert ok is True


# ---------------------------------------------------------------------------
# Allowlist match / miss.
# ---------------------------------------------------------------------------

def test_allowlist_match_observo_accepted(monkeypatch):
    """`https://p01-api.observo.ai` matches `*.observo.ai` and resolves
    to a public IP → accepted."""
    monkeypatch.setattr("socket.getaddrinfo", _make_getaddrinfo("8.8.8.8"))

    ok, reason = validate_url_for_ssrf(
        "https://p01-api.observo.ai/gateway/v1/pipelines",
        host_allowlist=OBSERVO_DEFAULT_ALLOWLIST,
    )
    assert ok is True, f"expected accept; reason={reason}"


def test_allowlist_miss_attacker_rejected(monkeypatch):
    """`https://attacker.example` does not match `*.observo.ai` and is
    rejected even though its resolved IP is public."""
    monkeypatch.setattr("socket.getaddrinfo", _make_getaddrinfo("8.8.8.8"))

    ok, reason = validate_url_for_ssrf(
        "https://attacker.example/api",
        host_allowlist=OBSERVO_DEFAULT_ALLOWLIST,
    )
    assert ok is False
    assert reason and "allowlist" in reason.lower()


def test_allowlist_miss_does_not_perform_dns(monkeypatch):
    """The allowlist check runs before DNS resolution, so a miss must
    not even reach `getaddrinfo`."""
    def _fail_dns(*_a, **_kw):
        raise AssertionError(
            "getaddrinfo must NOT be called for an off-allowlist hostname"
        )
    monkeypatch.setattr("socket.getaddrinfo", _fail_dns)

    ok, reason = validate_url_for_ssrf(
        "https://attacker.example/api",
        host_allowlist=OBSERVO_DEFAULT_ALLOWLIST,
    )
    assert ok is False
    assert reason


# ---------------------------------------------------------------------------
# Edge cases: scheme + structure.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/",
        "file:///etc/passwd",
        "gopher://example.com/",
        "javascript:alert(1)",
    ],
)
def test_disallowed_schemes(url, monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", _make_getaddrinfo("8.8.8.8"))

    ok, reason = validate_url_for_ssrf(url)
    assert ok is False
    assert reason and "scheme" in reason.lower()


def test_module_constant_is_observo_default():
    assert OBSERVO_DEFAULT_ALLOWLIST == ("*.observo.ai",)
