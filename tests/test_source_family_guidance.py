"""G.1 — source_family_registry wiring into _build_source_specific_guidance.

Plan reference: Stream G — OOS work completion (post-merge), sub-stream G.1.

Pre-G.1, ``_build_source_specific_guidance`` hardcoded guidance for only 3
vendors (Duo, Defender, Akamai). This suite asserts:

1. The four legacy vendor branches still emit their required substrings
   (substring match, NOT byte-equality — the registry's Defender entry
   intentionally adds an extra Defender-for-Cloud line that the legacy
   hardcode lacked).
2. Five additional vendors (Okta, Cloudflare, Apache HTTP, Microsoft 365,
   GCP Audit) now produce vendor-specific guidance via synthesis from
   ``default_notes`` + ``default_field_aliases`` when ``guidance_directives``
   is empty.
3. Unknown vendors still fall back to the single-line generic message.
"""

from __future__ import annotations

from components.agentic_lua_generator import _build_source_specific_guidance


# ---------------------------------------------------------------------------
# Legacy vendor branches — substrings preserved
# ---------------------------------------------------------------------------


def test_duo_legacy_required_lines_preserved():
    out = _build_source_specific_guidance(
        parser_name="cisco_duo_admin",
        vendor="Cisco",
        product="Duo",
        class_uid=3002,
        class_name="Authentication",
    )
    # Each substring must be present from the legacy 4-line Duo block at
    # agentic_lua_generator.py:607-611.
    for substring in [
        "Cisco Duo",
        "prioritize authentication semantics",
        "class_uid=3002",
        "actor.user.name",
        "src_endpoint.ip",
        "auth method/MFA",
    ]:
        assert substring in out, f"Duo legacy substring missing: {substring!r}"


def test_defender_legacy_required_lines_preserved_plus_for_cloud_addition():
    out = _build_source_specific_guidance(
        parser_name="microsoft_defender_alerts",
        vendor="Microsoft",
        product="Defender",
        class_uid=2001,
        class_name="Security Finding",
    )
    # Legacy 3-line Defender block at agentic_lua_generator.py:614-617.
    for substring in [
        "Microsoft Defender",
        "ActionType",
        "ProcessName",
        "activity_name",
        "process/device/network evidence",
    ]:
        assert substring in out, f"Defender legacy substring missing: {substring!r}"
    # Registry intentionally adds an extra Defender-for-Cloud directive
    # (source_family_registry.py:62). Documented as an improvement, not
    # a regression.
    assert "Defender for Cloud" in out, (
        "Registry's Defender-for-Cloud directive missing — expected enrichment "
        "from the registry over the legacy 3-line hardcode."
    )


def test_akamai_dns_legacy_required_lines_preserved():
    out = _build_source_specific_guidance(
        parser_name="akamai_dns_query_logs",
        vendor="Akamai",
        product="DNS",
        class_uid=4003,
        class_name="DNS Activity",
    )
    # Legacy 5-line Akamai DNS block at agentic_lua_generator.py:621-626.
    for substring in [
        "Akamai DNS",
        "DNS Activity",
        "class_uid=4003",
        "DNS query/answer/rcode",
        "cliIP",
        "src_endpoint.ip",
        "domain",
        "query.hostname",
        "recordType",
        "responseCode",
    ]:
        assert substring in out, f"Akamai DNS legacy substring missing: {substring!r}"


def test_akamai_cdn_legacy_required_lines_preserved():
    out = _build_source_specific_guidance(
        parser_name="akamai_cdn_http_logs",
        vendor="Akamai",
        product="CDN",
        class_uid=4002,
        class_name="HTTP Activity",
    )
    # Legacy 4-line Akamai CDN/HTTP block at agentic_lua_generator.py:629-633.
    for substring in [
        "Akamai CDN/HTTP",
        "HTTP Activity",
        "class_uid=4002",
        "method/host/path",
        "cliIP",
        "reqMethod",
        "http_request.http_method",
        "responseCode",
    ]:
        assert substring in out, f"Akamai CDN legacy substring missing: {substring!r}"


# ---------------------------------------------------------------------------
# Newly-active vendors — registry surfaces guidance via notes/aliases
# ---------------------------------------------------------------------------


def test_okta_guidance_now_appears():
    """Pre-G.1: Okta hit the generic fallback. Post-G.1: registry's Okta
    entry has empty ``guidance_directives`` BUT non-empty ``default_notes``
    + ``default_field_aliases``, which the synthesis path surfaces.
    """
    out = _build_source_specific_guidance(
        parser_name="okta_logs-latest",
        vendor="Okta",
        product="Identity Cloud",
        class_uid=3002,
        class_name="Authentication",
    )
    # Synthesized line from default_notes (registry line 239).
    assert "okta" in out.lower()
    assert "authentication" in out.lower() or "session" in out.lower()
    # Mapping hints from default_field_aliases (registry lines 242-246).
    assert "eventType" in out
    assert "ipAddress" in out
    # And critically: this is NOT the generic fallback line.
    assert "avoid generic catch-all" not in out


def test_cloudflare_guidance_now_appears():
    out = _build_source_specific_guidance(
        parser_name="cloudflare_inc_waf-lastest",
        vendor="Cloudflare",
        product="WAF",
        class_uid=4002,
        class_name="HTTP Activity",
    )
    # Synthesized from default_notes (registry line 253).
    assert "cloudflare" in out.lower()
    assert "WAF" in out or "http.request" in out
    # Mapping hints (registry lines 256-260).
    assert "client.ipAddress" in out
    assert "src_endpoint.ip" in out
    assert "avoid generic catch-all" not in out


def test_apache_http_guidance_now_appears():
    out = _build_source_specific_guidance(
        parser_name="apache_http_access",
        vendor="Apache",
        product="HTTPD",
        class_uid=4002,
        class_name="HTTP Activity",
    )
    # W2 backfill (2026-04-29): apache_http now carries non-empty
    # guidance_directives, so the assembled output is sourced from those
    # directives (CLF/Combined Log Format guidance) rather than from the
    # default_notes "raw log lines or key=value" string. Assert on the
    # populated guidance signature instead.
    assert "apache" in out.lower()
    assert (
        "Common Log Format" in out
        or "http_request.url.path" in out
        or "%h" in out
    )
    # Mapping hints (still emitted via default_field_aliases).
    assert "src_ip" in out
    assert "user_agent" in out
    assert "avoid generic catch-all" not in out


def test_microsoft_365_guidance_now_appears():
    """Microsoft 365 has rich ``guidance_directives`` (registry lines
    117-123) AND ``default_field_aliases``. Both should surface."""
    out = _build_source_specific_guidance(
        parser_name="microsoft_365_management_activity",
        vendor="Microsoft",
        product="Office 365",
        class_uid=3002,
        class_name="Authentication",
    )
    # From guidance_directives (registry line 117 onwards).
    assert "Microsoft 365" in out or "O365" in out
    assert "Graph" in out or "Management Activity" in out
    # Mapping hints from default_field_aliases (registry lines 130-144).
    assert "Operation" in out
    assert "avoid generic catch-all" not in out


def test_gcp_audit_guidance_now_appears():
    """GCP Audit's matcher requires both 'gcp' and 'audit' in the combined
    text (registry lines 148-152). Verify the directives flow through."""
    out = _build_source_specific_guidance(
        parser_name="gcp_audit_admin_activity",
        vendor="Google",
        product="GCP Audit",
        class_uid=3001,
        class_name="Account Change",
    )
    assert "GCP Audit" in out
    assert "logName" in out
    assert "protoPayload" in out
    assert "avoid generic catch-all" not in out


# ---------------------------------------------------------------------------
# Fallback path
# ---------------------------------------------------------------------------


def test_unknown_vendor_falls_back_to_generic():
    out = _build_source_specific_guidance(
        parser_name="random_unknown_parser",
        vendor="acme",
        product="widgets",
        class_uid=1234,
        class_name="Some Class",
    )
    assert "Source-specific guidance" in out
    assert "Some Class" in out
    assert "class_uid=1234" in out
    assert "avoid generic catch-all output" in out
