"""Central registry for source-family prompt guidance and mapping hints.

This keeps high-value serializer knowledge in one deterministic place so the
prompt builder can scale without accumulating more hardcoded branches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


Matcher = Callable[[str], bool]


@dataclass(frozen=True)
class SourceFamilyProfile:
    key: str
    matcher: Matcher
    guidance_directives: List[str]
    default_notes: List[str]
    default_field_aliases: List[str]


def _contains(term: str) -> Matcher:
    return lambda combined: term in combined


def _all_terms(*terms: str) -> Matcher:
    return lambda combined: all(term in combined for term in terms)


SOURCE_FAMILY_PROFILES: List[SourceFamilyProfile] = [
    SourceFamilyProfile(
        key="cisco_duo",
        matcher=_contains("duo"),
        guidance_directives=[
            "- Source-specific guidance (Cisco Duo): prioritize authentication semantics",
            "- Enforce `class_uid=3002` and authentication activity naming based on auth outcome",
            "- Map `actor.user.name` from user/account fields and `src_endpoint.ip` from client/source IP",
            "- Map status/auth method/MFA details when present (do not collapse into generic finding output)",
        ],
        default_notes=[
            "Cisco Duo samples are usually direct authentication events, not findings",
        ],
        default_field_aliases=[
            "status -> status",
            "src.ip -> src_endpoint.ip",
        ],
    ),
    SourceFamilyProfile(
        key="microsoft_defender",
        matcher=lambda combined: (
            "defender" in combined
            or "mdatp" in combined
            or "microsoft_365_defender" in combined
        ),
        guidance_directives=[
            "- Source-specific guidance (Microsoft Defender): use ActionType/ProcessName/Device* fields directly",
            "- Derive `activity_name` from ActionType and prefer concrete finding title/uid over placeholders",
            "- Preserve process/device/network evidence as mapped OCSF fields before fallback to `unmapped`",
            "- For Microsoft Defender for Cloud style alerts, prefer `id`/`providerAlertId`/`title`/`description`/`recommendedActions`/`tenantId`/`createdDateTime` as the canonical finding fields",
            "- Treat `evidence[*].@odata.type` as a routing signal for evidence/resource shaping instead of flattening all evidence into generic unmapped output",
        ],
        default_notes=[
            "Microsoft Defender samples often encode the core action in ActionType",
            "Microsoft Defender for Cloud alerts use id/title/description/recommendedActions/evidence as the canonical finding structure",
        ],
        default_field_aliases=[
            "Timestamp -> time source",
            "DeviceName -> device.hostname",
            "AccountName -> actor.user.name",
            "id -> metadata.uid or finding_info.uid",
            "providerAlertId -> finding_info.uid or unmapped.providerAlertId",
            "title -> finding_info.title",
            "description -> finding_info.desc",
            "recommendedActions -> remediation.desc",
            "tenantId -> cloud.account.uid",
            "createdDateTime -> time or finding_info.created_time",
            "firstActivityDateTime -> start_time",
            "lastActivityDateTime -> end_time",
            "evidence.@odata.type -> evidence/resource shaping",
        ],
    ),
    SourceFamilyProfile(
        key="netskope",
        matcher=_contains("netskope"),
        guidance_directives=[
            "- Source-specific guidance (Netskope): determine the subtype from `alert_type` before mapping fields",
            "- Prefer Netskope subtype routing defaults: `Policy` -> Web Resources Activity (6001); `DLP`, `UBA`, `Malware`, `Malsite`, `Security Assessment`, and `Compromised Credential` -> Security Finding (2001)",
            "- Preserve `policy`/`policy_id` as analytic or policy context, and preserve `srcip`/`dstip`/`url`/`alert_name` before falling back to `unmapped`",
            "- When Netskope records contain family-specific resource or evidence objects, keep them structured rather than collapsing them into a generic message-only event",
        ],
        default_notes=[
            "Netskope records should route on alert_type before final class/activity selection",
            "Policy events should prefer Web Resources Activity semantics over generic findings",
            "DLP, UBA, Malware, Malsite, Security Assessment, and Compromised Credential events should prefer Security Finding semantics",
        ],
        default_field_aliases=[
            "alert_type -> subtype router before mapping",
            "alert_name -> finding_info.title or malware.name depending on subtype",
            "policy -> analytic.name or actor.authorizations.policy.name",
            "policy_id -> analytic.uid or actor.authorizations.policy.uid",
            "srcip -> src_endpoint.ip",
            "dstip -> dst_endpoint.ip",
            "url -> web_resource.url_string or resource context",
            "timestamp -> time or metadata.original_time",
        ],
    ),
    SourceFamilyProfile(
        key="microsoft_365",
        matcher=lambda combined: (
            "microsoft 365" in combined
            or "o365" in combined
            or "office 365" in combined
        ),
        guidance_directives=[
            "- Source-specific guidance (Microsoft 365/O365): first distinguish Graph-style alerts from Management Activity records",
            "- Treat Graph-style alerts as finding-oriented records driven by `createdDateTime`, `vendorInformation`, `title`, `category`, and `status`",
            "- Treat Management Activity records as operation-driven records keyed by `Operation`, `Workload`, `CreationTime`, `UserId`, `Actor`, `Target`, `DeviceProperties`, and `AppAccessContext`",
            "- For Management Activity events, derive class and activity from the normalized operation name: sign-in -> Authentication, group/user changes -> IAM classes, DLP operations -> Security Finding",
            "- Preserve `PolicyDetails`, `SharePointMetaData`, `DeviceProperties`, `Actor`, `Target`, and `AppAccessContext` as structured mapping hints instead of flattening them into a generic message-only event",
        ],
        default_notes=[
            "Microsoft 365 inputs should first route to Graph alerts vs Management Activity logs",
            "Graph alerts are usually finding-oriented and use createdDateTime/title/category/status/vendorInformation",
            "Management Activity logs should derive class/activity from Operation and preserve Actor/Target/DeviceProperties/AppAccessContext structures",
        ],
        default_field_aliases=[
            "createdDateTime -> time or metadata.original_time",
            "vendorInformation.provider -> metadata.product.name",
            "title -> finding_info.title",
            "category -> finding_info.types or family hint",
            "status -> activity_name or status/status_detail context",
            "Operation -> subtype router before mapping",
            "CreationTime -> time or metadata.original_time",
            "UserId -> actor.user.email_addr or actor.user.uid",
            "Actor[].ID -> actor.user.email_addr or actor.user.uid",
            "Target[].ID -> user.uid or user.email_addr",
            "ClientIP or ActorIpAddress -> src_endpoint.ip",
            "DeviceProperties.SessionId -> actor.session.uid",
            "PolicyDetails.PolicyId -> analytic.uid",
            "PolicyDetails.PolicyName -> analytic.name",
        ],
    ),
    SourceFamilyProfile(
        key="gcp_audit",
        matcher=lambda combined: (
            "gcp audit" in combined
            or "google cloud audit" in combined
            or ("gcp" in combined and "audit" in combined)
        ),
        guidance_directives=[
            "- Source-specific guidance (GCP Audit): infer the event family from `logName` before setting class/activity values",
            "- Prefer these GCP families unless contradicted by the sample: `admin_activity`, `data_access`, `system_event`, and `policy_denied`",
            "- Map `protoPayload.authenticationInfo.principalEmail`, `protoPayload.requestMetadata.callerIp`, `protoPayload.serviceName`, `protoPayload.resourceName`, and `protoPayload.status.*` directly before using `unmapped`",
            "- For `policy_denied`, preserve status code/message/details and resource-oriented IAM semantics explicitly",
        ],
        default_notes=[
            "GCP Audit logs should route on logName-derived family: admin_activity, data_access, system_event, or policy_denied",
            "Policy denied records should preserve status code/message/details as first-class fields",
            "Map protoPayload actor/device/api/resource fields directly before copying residual fields to unmapped",
        ],
        default_field_aliases=[
            "logName -> subtype router before mapping",
            "protoPayload.authenticationInfo.principalEmail -> actor.user.email_addr",
            "protoPayload.requestMetadata.callerIp -> device.ip or src_endpoint.ip",
            "protoPayload.serviceName -> api.service.name",
            "protoPayload.resourceName -> entity.name or resource.name",
            "protoPayload.status.code -> status_code",
            "protoPayload.status.message -> status",
            "protoPayload.status.details -> status_detail",
            "timestamp -> time or metadata.original_time",
            "receiveTimestamp -> metadata.logged_time",
            "insertId -> metadata.uid",
        ],
    ),
    SourceFamilyProfile(
        key="darktrace",
        matcher=_contains("darktrace"),
        guidance_directives=[
            "- Source-specific guidance (Darktrace): determine the subtype from the record shape before mapping fields",
            "- Prefer these Darktrace families unless contradicted by the sample: `aianalyst/groups`, `aianalyst/incidentevents`, `modelbreaches`, and `status`",
            "- `groups`, `incidentevents`, and `modelbreaches` are usually finding-oriented records; `status` is usually device/state telemetry",
            "- Preserve `incidentEvents`, `relatedBreaches`, `breachDevices`, `model`, `triggeredComponents`, and `subnetData` as structured hints instead of flattening them away",
        ],
        default_notes=[
            "Darktrace records should route on record shape: groups, incidentevents, modelbreaches, or status",
            "AI Analyst groups/incidents and model breaches are usually finding-oriented; status records are usually device config/state telemetry",
            "Use incidentEvents/relatedBreaches/breachDevices/model/subnetData as primary structured hints before falling back to unmapped",
        ],
        default_field_aliases=[
            "start -> time or start_time",
            "end -> end_time",
            "incidentEvents[].uuid -> finding_info.uid",
            "incidentEvents[].title -> finding_info.title",
            "relatedBreaches[].modelName -> analytic.name or finding context",
            "breachDevices[].hostname -> device.hostname",
            "breachDevices[].ip -> device.ip",
            "model.then/model.now -> resources/resources_result",
            "ipAddress -> device.ip",
            "subnetData[].sid -> device.subnet_uid",
        ],
    ),
    SourceFamilyProfile(
        key="akamai_dns",
        matcher=_all_terms("akamai", "dns"),
        guidance_directives=[
            "- Source-specific guidance (Akamai DNS): target DNS Activity semantics",
            "- Enforce `class_uid=4003` and map DNS query/answer/rcode/src fields when available",
            "- Parse key/value pairs embedded in message text when structured fields are missing",
            "- Treat Akamai DNS aliases explicitly: `cliIP`->`src_endpoint.ip`, `domain`->`query.hostname`, `recordType`->`query.type`, `responseCode`->`rcode`/`rcode_id`",
            "- If `cliIP` is present in message payload, `src_endpoint.ip` must not be left blank",
        ],
        default_notes=[
            "Akamai DNS samples often embed key=value fields in message; parse them first",
        ],
        default_field_aliases=[],
    ),
    SourceFamilyProfile(
        key="akamai_http",
        matcher=lambda combined: "akamai" in combined and ("cdn" in combined or "http" in combined),
        guidance_directives=[
            "- Source-specific guidance (Akamai CDN/HTTP): target HTTP Activity semantics",
            "- Enforce `class_uid=4002` and map method/host/path/status/src_ip/user_agent where available",
            "- Parse key/value pairs embedded in message text when structured fields are missing",
            "- Treat Akamai HTTP aliases explicitly: `cliIP`->`src_endpoint.ip`, `reqMethod`->`http_request.http_method`, `reqHost`/`domain`->`http_request.url` or host context, `responseCode`->`http_response.code`",
        ],
        default_notes=[
            "Akamai HTTP/CDN samples often embed key=value fields in message; parse them first",
        ],
        default_field_aliases=[],
    ),
    SourceFamilyProfile(
        key="okta",
        matcher=_contains("okta"),
        guidance_directives=[
            "- Source-specific guidance (Okta): Okta system-log records are authentication/identity events; route on `eventType` before mapping",
            "- Prefer `class_uid=3002` (Authentication) for `user.session.start`, `user.session.end`, and `user.authentication.*` events; use `class_uid=3001` (Account Change) for `user.lifecycle.*` and `group.user_membership.*` operations; use `class_uid=2001` (Security Finding) only for risk/security signals",
            "- Map `actor.alternateId`/`actor.displayName` to `actor.user.email_addr`/`actor.user.name` and `client.ipAddress`/`request.ipChain[0].ip` to `src_endpoint.ip`",
            "- Derive `activity_id` and `status` from `outcome.result` (SUCCESS -> 1, FAILURE -> 2, ALLOW/DENY mapped on the deny axis when present); preserve `outcome.reason` as `status_detail`",
            "- Preserve `authenticationContext`, `securityContext`, `debugContext.debugData`, `target[]` (with `id`/`type`/`alternateId`/`displayName`), and `transaction.id` as structured hints — never collapse them into `unmapped` only",
        ],
        default_notes=[
            "Okta samples are usually authentication/session events with useful eventType semantics",
            "Route on eventType prefix: user.session.* and user.authentication.* are 3002; user.lifecycle.* and group.user_membership.* are 3001; risk/security events route to 2001",
        ],
        default_field_aliases=[
            "eventType -> activity_name or status_detail context",
            "actor.type -> actor.user.type_id or user context",
            "actor.alternateId -> actor.user.email_addr",
            "actor.displayName -> actor.user.name",
            "actor.id -> actor.user.uid",
            "client.ipAddress -> src_endpoint.ip",
            "client.userAgent.rawUserAgent -> http_request.user_agent",
            "client.geographicalContext.country -> src_endpoint.location.country",
            "request.ipChain[0].ip -> src_endpoint.ip",
            "outcome.result -> status (SUCCESS -> 1, FAILURE -> 2)",
            "outcome.reason -> status_detail",
            "ipAddress -> src_endpoint.ip",
            "displayMessage -> message",
            "transaction.id -> metadata.uid or transaction.uid",
            "authenticationContext.authenticationProvider -> auth_protocol context",
            "target[].alternateId -> user.email_addr or resource.uid",
            "target[].displayName -> user.name or resource.name",
            "published -> time or metadata.original_time",
        ],
    ),
    SourceFamilyProfile(
        key="cloudflare",
        matcher=_contains("cloudflare"),
        guidance_directives=[
            "- Source-specific guidance (Cloudflare): determine the subtype from the record shape before mapping fields",
            "- Prefer `class_uid=4002` (HTTP Activity) for HTTP request logs and access events; use `class_uid=2001` (Security Finding) for WAF, firewall, bot-management, and rate-limiting blocks; use `class_uid=4002` with security context when the record carries both http_request and security action",
            "- Map `ClientIP`/`client.ipAddress` -> `src_endpoint.ip`, `EdgeServerIP` -> `dst_endpoint.ip`, `ClientRequestMethod`/`http.request.method` -> `http_request.http_method`, `ClientRequestURI`/`ClientRequestPath` -> `http_request.url.path`, `EdgeResponseStatus`/`edge_response_status` -> `http_response.code`",
            "- Preserve `RayID`/`ray_id` as `metadata.uid` so operators can pivot back to the Cloudflare console; preserve `ZoneName`/`zone` as `web_resource.url_string` host or `domain`",
            "- For WAF/firewall events, preserve `WAFAction`/`waf_action`/`Action` as `disposition_id`/`disposition`, `WAFRuleID`/`waf_rule_id` as `analytic.uid`, and `WAFRuleMessage`/`waf_rule_message` as `finding_info.title`",
            "- Treat `ClientCountry`/`client_country` as `src_endpoint.location.country`; do not flatten geo fields away into `unmapped`",
        ],
        default_notes=[
            "Cloudflare WAF samples are typically HTTP request/security events; prefer client and http.request fields",
            "WAF/firewall blocks should route to Security Finding 2001; access logs and successful HTTP requests should route to HTTP Activity 4002",
            "Always preserve RayID as metadata.uid for Cloudflare console pivot",
        ],
        default_field_aliases=[
            "client.ipAddress -> src_endpoint.ip",
            "ClientIP -> src_endpoint.ip",
            "ClientCountry -> src_endpoint.location.country",
            "client_country -> src_endpoint.location.country",
            "ClientRequestUserAgent -> http_request.user_agent",
            "user_agent -> http_request.user_agent",
            "http.request.method -> http_request.http_method",
            "ClientRequestMethod -> http_request.http_method",
            "http_method -> http_request.http_method",
            "ClientRequestURI -> http_request.url.path",
            "ClientRequestPath -> http_request.url.path",
            "http_path -> http_request.url.path",
            "ClientRequestHost -> http_request.url.hostname",
            "http_host -> http_request.url.hostname",
            "EdgeResponseStatus -> http_response.code",
            "edge_response_status -> http_response.code",
            "RayID -> metadata.uid",
            "ray_id -> metadata.uid",
            "ZoneName -> web_resource.url_string host",
            "zone -> web_resource.url_string host",
            "WAFAction -> disposition_id or disposition",
            "waf_action -> disposition_id or disposition",
            "WAFRuleID -> analytic.uid",
            "waf_rule_id -> analytic.uid",
            "WAFRuleMessage -> finding_info.title",
            "waf_rule_message -> finding_info.title",
            "EdgeStartTimestamp -> time or metadata.original_time",
            "eventType -> activity_name",
            "outcome.result -> status",
        ],
    ),
    SourceFamilyProfile(
        key="apache_http",
        matcher=_contains("apache"),
        guidance_directives=[
            "- Source-specific guidance (Apache HTTP): target HTTP Activity (4002) semantics directly",
            "- Enforce `class_uid=4002` and derive `activity_id` from request method (GET=1, POST=2, PUT=3, DELETE=4, HEAD=5, etc.); set `severity_id=1` (Informational) by default",
            "- Common Log Format (CLF) and Combined Log Format payloads are positional; parse them deterministically before falling back to `unmapped`: `host ident authuser [time] \"method uri proto\" status bytes \"referer\" \"user-agent\"`",
            "- Map `src_ip`/`remote_host`/`%h` -> `src_endpoint.ip`, `method`/`%m` -> `http_request.http_method`, `uri`/`%U` -> `http_request.url.path`, `query`/`%q` -> `http_request.url.query_string`, `status`/`%s` -> `http_response.code`, `bytes`/`%b` -> `http_response.length`",
            "- Preserve `user_agent`/`%{User-Agent}i`, `referer`/`%{Referer}i`, `authuser`/`%u`, and `proto`/`%H` as first-class fields; do not collapse them into a generic message",
            "- Treat 4xx/5xx status codes as `status_id=2` (Failure) and successful 2xx/3xx as `status_id=1` (Success)",
        ],
        default_notes=[
            "Apache HTTP samples may be raw log lines or key=value lines; prioritize src, method, uri, status, bytes, user_agent",
            "Common Log Format and Combined Log Format are positional; parse positions deterministically before falling back to unmapped",
            "Map status code to status_id: 2xx/3xx -> 1 (Success), 4xx/5xx -> 2 (Failure)",
        ],
        default_field_aliases=[
            "src_ip -> src_endpoint.ip",
            "remote_host -> src_endpoint.ip",
            "%h -> src_endpoint.ip",
            "method -> http_request.http_method",
            "%m -> http_request.http_method",
            "uri -> http_request.url.path",
            "%U -> http_request.url.path",
            "query -> http_request.url.query_string",
            "%q -> http_request.url.query_string",
            "proto -> http_request.version",
            "%H -> http_request.version",
            "status -> http_response.code or status",
            "%s -> http_response.code",
            "bytes -> http_response.length",
            "%b -> http_response.length",
            "user_agent -> http_request.user_agent",
            "%{User-Agent}i -> http_request.user_agent",
            "referer -> http_request.referrer",
            "%{Referer}i -> http_request.referrer",
            "authuser -> actor.user.name",
            "%u -> actor.user.name",
            "time -> time or metadata.original_time",
            "%t -> time",
        ],
    ),
    SourceFamilyProfile(
        key="windows_event_auth",
        matcher=lambda combined: "windows_event" in combined or "new_device" in combined,
        guidance_directives=[
            "- Source-specific guidance (Windows Event Auth): target Authentication (3002) semantics for sign-in events",
            "- Map Windows event IDs explicitly: 4624 (logon success) -> `activity_id=1`, `status_id=1`; 4625 (logon failure) -> `activity_id=1`, `status_id=2`; 4634/4647 (logoff) -> `activity_id=2`; 4648 (explicit credential logon) -> `activity_id=1` with `auth_protocol` context",
            "- Map `EventID` -> `metadata.event_code`, `Channel`/`LogName` -> `metadata.product.feature.name`, `Computer`/`device.hostname` -> `dst_endpoint.hostname`",
            "- Map `TargetUserName`/`actor.email` -> `actor.user.name`/`actor.user.email_addr`, `TargetDomainName` -> `actor.user.domain`, `IpAddress`/`client.ip_address` -> `src_endpoint.ip`, `WorkstationName` -> `src_endpoint.hostname`",
            "- Preserve `LogonType` as a routing signal (2=Interactive, 3=Network, 10=RemoteInteractive) and surface it in `auth_protocol` or as `logon_type` in unmapped only when no canonical OCSF slot exists",
            "- Preserve `ProcessName`, `LogonProcessName`, `AuthenticationPackageName` as authentication context; preserve `SubStatus`/`Status` hex codes as `status_code`/`status_detail`",
        ],
        default_notes=[
            "Windows-event-style auth samples can still be authentication events; use actor/client/authentication/risk fields directly",
            "Event IDs 4624 (logon success), 4625 (logon failure), 4634/4647 (logoff) are the dominant 3002 mappings",
            "LogonType is a routing signal: 2=Interactive, 3=Network, 10=RemoteInteractive",
        ],
        default_field_aliases=[
            "actor.email -> actor.user.email_addr",
            "TargetUserName -> actor.user.name",
            "TargetDomainName -> actor.user.domain",
            "TargetUserSid -> actor.user.uid",
            "SubjectUserName -> actor.user.name",
            "client.ip_address -> src_endpoint.ip",
            "IpAddress -> src_endpoint.ip",
            "WorkstationName -> src_endpoint.hostname",
            "client.user_agent -> http_request.user_agent or observables context",
            "Computer -> dst_endpoint.hostname",
            "EventID -> metadata.event_code",
            "Channel -> metadata.product.feature.name",
            "LogName -> metadata.product.feature.name",
            "LogonType -> auth_protocol context or logon_type",
            "LogonProcessName -> actor.process.name",
            "AuthenticationPackageName -> auth_protocol",
            "ProcessName -> actor.process.file.path",
            "Status -> status_code",
            "SubStatus -> status_detail",
            "outcome.result -> status",
            "TimeCreated -> time or metadata.original_time",
        ],
    ),
]


def build_combined_source_text(
    parser_name: str,
    vendor: str,
    product: str,
    declared_log_type: str,
    declared_log_detail: str,
) -> str:
    return f"{parser_name} {vendor} {product} {declared_log_type} {declared_log_detail}".lower()


def find_source_family_profile(
    parser_name: str,
    vendor: str,
    product: str,
    declared_log_type: str,
    declared_log_detail: str,
) -> Optional[SourceFamilyProfile]:
    combined = build_combined_source_text(
        parser_name, vendor, product, declared_log_type, declared_log_detail
    )
    for profile in SOURCE_FAMILY_PROFILES:
        if profile.matcher(combined):
            return profile
    return None


def find_source_family_guidance_profiles(
    parser_name: str,
    vendor: str,
    product: str,
    declared_log_type: str,
    declared_log_detail: str,
) -> List[SourceFamilyProfile]:
    combined = build_combined_source_text(
        parser_name, vendor, product, declared_log_type, declared_log_detail
    )
    return [profile for profile in SOURCE_FAMILY_PROFILES if profile.matcher(combined)]


def list_supported_source_family_keys() -> List[str]:
    return [profile.key for profile in SOURCE_FAMILY_PROFILES]


def apply_source_family_defaults(
    defaults: Dict[str, object],
    parser_name: str,
    vendor: str,
    product: str,
    declared_log_type: str,
    declared_log_detail: str,
) -> Dict[str, object]:
    profile = find_source_family_profile(
        parser_name, vendor, product, declared_log_type, declared_log_detail
    )
    if not profile:
        return defaults
    notes = defaults.setdefault("notes", [])
    aliases = defaults.setdefault("field_aliases", [])
    notes.extend(profile.default_notes)
    aliases.extend(profile.default_field_aliases)
    return defaults
