#!/usr/bin/env python3
"""Generate synthetic DNS query logs (JSON format for /event HEC endpoint).

Uses OCSF-style fields consistent with the observo_paloalto_firewall generator.
Source IPs drawn from the fixed ascension lookup IP pool for enrichment.
"""
import random
import ipaddress
from datetime import datetime, timezone, timedelta

# Fixed IP pool from ascension_lookup.csv
IP_POOL = [
    "10.0.0.10", "10.0.0.102", "10.0.1.122", "10.0.1.29", "10.0.1.54",
    "10.0.1.80", "10.0.2.12", "10.0.2.133", "10.0.2.238", "10.0.2.43",
    "10.0.2.53", "10.0.2.65", "10.0.3.117", "10.0.3.152", "10.0.3.159",
    "10.0.3.237", "10.0.3.242", "10.0.3.55", "10.0.3.81", "10.0.4.139",
    "10.0.4.201", "10.0.4.227", "108.161.138.152", "129.144.62.179",
    "172.16.1.111", "172.16.1.172", "172.16.1.200", "172.16.1.232",
    "172.16.1.250", "172.16.1.86", "172.16.2.130", "172.16.2.230",
    "172.16.2.242", "172.16.2.29", "172.16.3.117", "172.16.3.134",
    "172.16.3.161", "172.16.3.164", "172.16.3.178", "172.16.3.195",
    "172.16.3.37", "188.146.131.155", "192.168.1.106", "192.168.1.174",
    "192.168.1.21", "192.168.1.32", "192.168.1.55", "192.168.10.53",
    "192.168.5.186", "192.168.5.187", "192.168.5.74", "192.168.5.79",
    "34.216.78.37", "34.217.108.226", "40.70.134.175", "51.15.82.93",
    "52.88.186.130",
]

# Internal DNS resolvers
DNS_RESOLVERS = ["10.0.2.53", "192.168.10.53"]

USERNAMES = [
    "corp\\admin.jthompson", "corp\\s.martinez", "corp\\l.chen", "corp\\d.patel",
    "corp\\r.nakamura", "corp\\j.oconnor", "corp\\k.washington", "corp\\a.garcia",
    "corp\\b.foster", "corp\\c.robertson", "corp\\m.johansson", "corp\\t.williams",
    "corp\\n.kim", "corp\\admin.rsingh", "corp\\e.vasquez", "corp\\h.tanaka",
    "corp\\p.anderson", "corp\\f.mueller", "corp\\v.popova", "corp\\j.brooks",
]

ZONES = ["trust", "untrust", "dmz", "internal", "external", "internet"]

# Query types
QUERY_TYPES = ["A", "AAAA", "CNAME", "MX", "PTR", "TXT", "SRV", "NS"]
QUERY_TYPE_WEIGHTS = [50, 15, 10, 5, 5, 5, 5, 5]

# Response codes
RCODES = ["NOERROR", "NXDOMAIN", "SERVFAIL", "REFUSED"]
RCODE_WEIGHTS = [85, 10, 3, 2]

# Actions matching rcode
RCODE_ACTIONS = {
    "NOERROR": "allow",
    "NXDOMAIN": "allow",
    "SERVFAIL": "deny",
    "REFUSED": "deny",
}

# Domains
LEGITIMATE_DOMAINS = [
    "google.com", "googleapis.com", "gstatic.com",
    "microsoft.com", "office365.com", "microsoftonline.com", "azure.com",
    "amazonaws.com", "aws.amazon.com", "s3.amazonaws.com",
    "github.com", "gitlab.com", "bitbucket.org",
    "slack.com", "zoom.us", "teams.microsoft.com",
    "cloudflare.com", "akamaiedge.net", "fastly.net",
    "okta.com", "auth0.com",
    "salesforce.com", "servicenow.com", "atlassian.net",
    "docker.io", "npmjs.org", "pypi.org",
    "sentinelone.net", "crowdstrike.com",
]

INTERNAL_DOMAINS = [
    "corp.local", "dc-primary-01.corp.local", "dc-secondary-01.corp.local",
    "mail.corp.local", "intranet.corp.local", "wiki.corp.local",
    "jira.corp.local", "gitlab.corp.local", "jenkins.corp.local",
    "payroll.corp.local", "crm.corp.local", "vpn.corp.local",
    "ldap.corp.local", "ntp.corp.local", "syslog.corp.local",
    "splunk.corp.local", "kafka.corp.local", "redis.corp.local",
    "db-mssql.corp.local", "backup.corp.local", "proxy.corp.local",
]

SUSPICIOUS_DOMAINS = [
    "xn--80ak6aa92e.com", "free-vpn-download.net", "crypto-mining-pool.org",
    "d4rkw3b-t00ls.net", "pastebin-raw.xyz", "temp-mail-service.ru",
    "fast-flux-c2.top", "dga-abcxyz123.biz", "exfil-dns.tk",
    "update-flash-player.info",
]

SEVERITIES = ["critical", "high", "medium", "low", "informational"]
THREAT_CATEGORIES = [
    "dns-c2", "dns-malware", "dns-phishing", "dns-grayware",
    "dns-parked", "dns-proxy-avoidance", "dns-dynamic-dns",
    "dns-newly-registered", "dns-benign",
]


def random_resolved_ip() -> str:
    """Generate a random public IP for DNS resolution answers."""
    while True:
        ip = ipaddress.IPv4Address(random.randint(1, 0xFFFFFFFF))
        if not (ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local or ip.is_multicast):
            return str(ip)


def observo_dns_query_log(overrides: dict | None = None) -> dict:
    """Generate a single DNS query log entry using OCSF-style fields."""
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(seconds=random.randint(0, 5))

    src_ip = random.choice(IP_POOL)
    dns_server = random.choice(DNS_RESOLVERS)
    src_port = random.randint(32768, 65535)

    # Pick domain category: 60% legitimate, 30% internal, 10% suspicious
    domain_roll = random.random()
    if domain_roll < 0.60:
        domain = random.choice(LEGITIMATE_DOMAINS)
        threat_category = "dns-benign"
        severity = "informational"
    elif domain_roll < 0.90:
        domain = random.choice(INTERNAL_DOMAINS)
        threat_category = "dns-benign"
        severity = "informational"
    else:
        domain = random.choice(SUSPICIOUS_DOMAINS)
        threat_category = random.choice(THREAT_CATEGORIES[:8])
        severity = random.choice(["critical", "high", "medium"])

    # Add subdomain variety
    if domain not in INTERNAL_DOMAINS and random.random() < 0.4:
        subdomain = random.choice(["www", "api", "cdn", "mail", "login", "app", "docs"])
        query_name = f"{subdomain}.{domain}"
    else:
        query_name = domain

    query_type = random.choices(QUERY_TYPES, weights=QUERY_TYPE_WEIGHTS)[0]
    rcode = random.choices(RCODES, weights=RCODE_WEIGHTS)[0]
    action = RCODE_ACTIONS[rcode]

    # Resolved IP for A record answers
    resolved_ip = random_resolved_ip() if rcode == "NOERROR" and query_type == "A" else ""
    ttl = random.choice([60, 300, 600, 1800, 3600, 86400]) if rcode == "NOERROR" else 0

    event = {
        "future_use_1": "",
        "receive_time": now.strftime("%Y/%m/%d %H:%M:%S"),
        "serial_number": f"{random.randint(100000000000000, 999999999999999)}",
        "type": "THREAT",
        "subtype": "dns",
        "future_use_2": "",
        "time_generated": start_time.strftime("%Y/%m/%d %H:%M:%S"),
        "src": src_ip,
        "dst": dns_server,
        "natsrc": src_ip,
        "natdst": dns_server,
        "rule": "dns-security",
        "srcuser": random.choice(USERNAMES),
        "dstuser": "",
        "app": "dns",
        "vsys": "vsys1",
        "from": random.choice(["trust", "internal", "vpn"]),
        "to": random.choice(["untrust", "external", "internet"]),
        "inbound_if": f"ethernet1/{random.randint(1, 8)}",
        "outbound_if": f"ethernet1/{random.randint(1, 8)}",
        "logset": "FORWARD",
        "future_use_3": "",
        "sessionid": str(random.randint(10000, 999999)),
        "repeatcnt": "1",
        "sport": str(src_port),
        "dport": "53",
        "natsport": str(src_port),
        "natdport": "53",
        "flags": "0x0",
        "proto": random.choices(["udp", "tcp"], weights=[95, 5])[0],
        "action": action,
        "query_name": query_name,
        "query_type": query_type,
        "rcode": rcode,
        "resolved_ip": resolved_ip,
        "ttl": str(ttl),
        "category": threat_category,
        "severity": severity,
        "direction": "client-to-server",
        "seqno": str(random.randint(1, 1000000)),
        "actionflags": "0x0",
        "srcloc": "",
        "dstloc": "",
        "future_use_5": "",
        "bytes": str(random.randint(60, 512)),
        "bytes_sent": str(random.randint(40, 200)),
        "bytes_received": str(random.randint(60, 512)),
        "packets": str(random.randint(1, 4)),
        "start": start_time.strftime("%Y/%m/%d %H:%M:%S"),
        "elapsed": "0",
        "pkts_sent": "1",
        "pkts_received": str(random.randint(1, 3)),
        "session_end_reason": "aged-out",
    }

    if overrides:
        event.update(overrides)

    return event


if __name__ == "__main__":
    import json
    print("Sample Observo DNS Query logs (OCSF-style JSON):")
    for i in range(5):
        log = observo_dns_query_log()
        print(f"\n--- Query {i+1} ({log['category']}: {log['query_name']}) ---")
        print(json.dumps(log, indent=2))
