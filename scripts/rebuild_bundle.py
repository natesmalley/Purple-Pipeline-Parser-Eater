#!/usr/bin/env python3
"""Rebuild transform_ocsf_bundle with grade promotion + REMEDIATION.md + GRADES.md."""

import json
from pathlib import Path

import yaml

BUNDLE = Path("output/transform_ocsf_bundle")
PENDING = BUNDLE / "_pending_remediation"


def promote_grade(transform_dir: Path) -> None:
    json_path = transform_dir / f"{transform_dir.name}.json"
    if not json_path.exists():
        return
    details = json.loads(json_path.read_text())
    v = details.get("validation", {})
    grade_obj = {
        "letter": v.get("harness_grade"),
        "score": v.get("harness_score"),
        "verdict": v.get("orion_verdict"),
        "required_field_coverage_pct": v.get("harness_required_coverage"),
        "source_field_coverage_pct": v.get("harness_field_coverage"),
        "tested_with_realistic_event": v.get("tested_with_realistic_event", False),
        "validated_at": v.get("validated_at"),
    }
    new_details = {
        "schema_version": details.get("schema_version"),
        "component": details.get("component"),
        "template_name": details.get("template_name"),
        "display_name": details.get("display_name"),
        "grade": grade_obj,
        "ocsf": details.get("ocsf"),
        "description": details.get("description"),
        "vendor": details.get("vendor"),
        "source_name": details.get("source_name"),
        "version": details.get("version"),
        "parameters": details.get("parameters"),
        "validation": v,
        "provenance": details.get("provenance"),
    }
    json_path.write_text(json.dumps(new_details, indent=2))

    md_path = transform_dir / "metadata.yaml"
    if md_path.exists():
        md = yaml.safe_load(md_path.read_text()) or {}
        if "grade" not in md:
            md = {"grade": grade_obj, "metadata_details": md.get("metadata_details", {})}
            md_path.write_text(
                yaml.dump(md, sort_keys=False, default_flow_style=False, width=100)
            )


def promote_all():
    count = 0
    for d in BUNDLE.iterdir():
        if d.is_dir() and d.name != "_pending_remediation":
            promote_grade(d)
            count += 1
    for d in PENDING.iterdir():
        if d.is_dir():
            promote_grade(d)
            count += 1
    return count


REMEDIATION = {
    "agent_metrics_logs": {
        "current_class": 1007,
        "target_class": 5001,
        "target_class_name": "Device Inventory Info",
        "target_category_uid": 5,
        "must_set": [
            "device.uid",
            "device.name",
            "device.agent_list[].name+version+type",
            "device.os.name",
            "metadata.product.name",
        ],
        "prompt_hint": (
            "Remap from 1007 to 5001 Device Inventory Info; source is agent self-telemetry; "
            "build device object with agent_list[] from agent name/version/type fields; set "
            "activity_id=1 (Log); never touch process fields."
        ),
    },
    "snyk": {
        "current_class": 2002,
        "target_class": 2002,
        "target_class_name": "Vulnerability Finding (keep)",
        "target_category_uid": 2,
        "must_set": [
            "finding_info.uid",
            "finding_info.title",
            "finding_info.created_time",
            "vulnerabilities[].cve.uid",
            "vulnerabilities[].severity",
        ],
        "prompt_hint": (
            "Class is correct; fix empty-input resilience — script MUST always emit a valid "
            "OCSF skeleton (class_uid, category_uid, activity_id, time, severity_id, "
            "finding_info stub) even when all source fields are nil; pcall wrapper must return "
            "skeleton not passthrough on empty event."
        ),
    },
    "microsoft_defender_for_cloud": {
        "current_class": 2004,
        "target_class": 2004,
        "target_class_name": "Detection Finding (keep)",
        "target_category_uid": 2,
        "must_set": [
            "finding_info.uid (alertId)",
            "finding_info.title (alertDisplayName)",
            "attacks[].tactic.name+technique.name (MITRE from tactics[])",
            "cloud.account.uid (subscriptionId)",
            "resources[].name (compromised entity)",
        ],
        "prompt_hint": (
            "Map Defender for Cloud alert schema: alertId->finding_info.uid, "
            "alertDisplayName->finding_info.title, tactics[]->attacks[], "
            "resourceIdentifiers[].azureResourceId->resources[], "
            "subscriptionId->cloud.account.uid; cloud object is required and currently absent."
        ),
    },
    "azure_ad": {
        "current_class": 3004,
        "target_class": 3001,
        "target_class_name": "Account Change",
        "target_category_uid": 3,
        "must_set": [
            "user.name (target UPN)",
            "user.uid (target objectId)",
            "actor.user.name (initiatedBy UPN)",
            "cloud.account.uid (tenantId)",
            "activity_id (1=Create/2=Read/3=Update/4=Delete/5=Enable/6=Disable)",
        ],
        "prompt_hint": (
            "Reclassify from 3004 to 3001 Account Change; map Azure AD audit "
            "operationType->activity_id, targetResources[0].userPrincipalName->user.name, "
            "targetResources[0].id->user.uid, "
            "initiatedBy.user.userPrincipalName->actor.user.name, tenantId->cloud.account.uid."
        ),
    },
    "aws_vpc_flow": {
        "current_class": 4001,
        "target_class": 4001,
        "target_class_name": "Network Activity (keep)",
        "target_category_uid": 4,
        "must_set": [
            "src_endpoint.ip (srcaddr)",
            "dst_endpoint.ip (dstaddr)",
            "src_endpoint.port (srcport)",
            "dst_endpoint.port (dstport)",
            "connection_info.protocol_num (protocol IANA int)",
            "traffic.bytes_out (bytes)",
            "action_id (ACCEPT->1 / REJECT->2)",
        ],
        "prompt_hint": (
            "Script is using wrong AWS VPC Flow v2 field names; map srcaddr->src_endpoint.ip, "
            "dstaddr->dst_endpoint.ip, srcport->src_endpoint.port, dstport->dst_endpoint.port, "
            "protocol (IANA int)->connection_info.protocol_num, bytes->traffic.bytes_out, "
            "packets->traffic.packets_out, action ACCEPT/REJECT->action_id 1/2, "
            "account-id->cloud.account.uid."
        ),
    },
    "proofpoint": {
        "current_class": 4012,
        "target_class": 2004,
        "target_class_name": "Detection Finding",
        "target_category_uid": 2,
        "must_set": [
            "finding_info.uid (GUID/messageId)",
            "finding_info.title (threatName/subject)",
            "actor.user.email_addr (sender)",
            "user.email_addr (recipient)",
            "evidences[].data (email artifact with subject/sender/URLs)",
        ],
        "prompt_hint": (
            "Reclassify from 4012 to 2004 Detection Finding; map Proofpoint TAP fields: "
            "GUID->finding_info.uid, threatName->finding_info.title, "
            "sender->actor.user.email_addr, recipient->user.email_addr, "
            "classification->finding_info.types[], threatUrl/malwareFamily->evidences[]; "
            "set cloud.provider=Proofpoint."
        ),
    },
    "tenable_vulnerability_management_audit_logging": {
        "current_class": 6001,
        "target_class": 2002,
        "target_class_name": "Vulnerability Finding",
        "target_category_uid": 2,
        "must_set": [
            "finding_info.uid (plugin_id)",
            "finding_info.title (plugin_name)",
            "vulnerabilities[].cve.uid (cve)",
            "vulnerabilities[].severity (severity string)",
            "resources[].name (hostname/ip_address)",
        ],
        "prompt_hint": (
            "Reclassify from 6001 to 2002 Vulnerability Finding; map plugin_id->finding_info.uid, "
            "plugin_name->finding_info.title, cve->vulnerabilities[].cve.uid, "
            "cvss_base_score->vulnerabilities[].cvss.base_score, "
            "severity->vulnerabilities[].severity + top-level severity_id, "
            "hostname/ip_address->resources[].name/ip, asset_id->resources[].uid."
        ),
    },
}


def write_remediations():
    count = 0
    for slug, plan in REMEDIATION.items():
        candidates = [
            p for p in PENDING.iterdir() if p.is_dir() and (p.name == slug or slug in p.name)
        ]
        if not candidates:
            print(f"  WARN: no dir for {slug}")
            continue
        d = candidates[0]
        lines = [
            f"# Remediation plan — `{d.name}`",
            "",
            "Source: Orion validation pass 2026-04-19.",
            "",
            "## Current state",
            f"- Class: **{plan['current_class']}**",
            f"- Harness grade: see `{d.name}.json` -> `grade`",
            "",
            "## Target state",
            (f"- Class: **{plan['target_class']} {plan['target_class_name']}** "
             f"(category_uid {plan['target_category_uid']})"),
            "",
            "## Required OCSF fields the Lua MUST emit",
            "",
        ]
        for f in plan["must_set"]:
            lines.append(f"- `{f}`")
        lines += [
            "",
            "## Regeneration prompt hint",
            "",
            f"> {plan['prompt_hint']}",
            "",
            "## Acceptance gates",
            "",
            "- [ ] Harness grade >= C (score >= 70)",
            "- [ ] Required-field coverage = 100%",
            "- [ ] Field coverage >= 60% against realistic HELIOS/Jarvis event",
            "- [ ] Orion verdict = `signed_off` on re-review",
            "- [ ] No `class_uid_concern` flag needed in manifest",
        ]
        (d / "REMEDIATION.md").write_text("\n".join(lines) + "\n")
        count += 1
    return count


def write_pending_readme():
    (PENDING / "README.md").write_text("""# _pending_remediation/

7 transforms flagged by Orion as having real script-level concerns. Each subdirectory contains a
`REMEDIATION.md` with current vs. target OCSF class, required fields, a prompt hint for
regeneration, and acceptance gates.

## Summary

| Transform | Current | Target | Action |
|---|---|---|---|
| agent_metrics_logs | 1007 | **5001** Device Inventory Info | Reclassify — metrics are device inventory, not process activity |
| snyk | 2002 | 2002 Vulnerability Finding (keep) | Fix empty-input resilience; emit OCSF skeleton even with nil input |
| microsoft_defender_for_cloud | 2004 | 2004 Detection Finding (keep) | Add finding_info.uid, attacks[], cloud.account.uid |
| azure_ad | 3004 | **3001** Account Change | Reclassify + map operationType->activity_id, tenantId->cloud.account.uid |
| aws_vpc_flow | 4001 | 4001 Network Activity (keep) | Fix field-name mapping for v2 format (srcaddr->src_endpoint.ip etc.) |
| proofpoint | 4012 | **2004** Detection Finding | Reclassify — TAP is threat detection, not URL activity |
| tenable_vulnerability_management_audit_logging | 6001 | **2002** Vulnerability Finding | Reclassify + map plugin_id, cve, severity properly |

Estimated batch-regeneration cost: ~$5 LLM credits, ~30 min runtime.
""")


def status_sort_key(status: str) -> int:
    return 0 if status == "active" else 1


def build_grades_md():
    rows = []
    for d in sorted(BUNDLE.iterdir()):
        if not d.is_dir() or d.name == "_pending_remediation":
            continue
        p = d / f"{d.name}.json"
        if p.exists():
            j = json.loads(p.read_text())
            g = j.get("grade") or {}
            rows.append((
                d.name, "active", g.get("letter"), g.get("score"), g.get("verdict"),
                j.get("ocsf", {}).get("class_uid"), g.get("required_field_coverage_pct", 0),
            ))
    for d in sorted(PENDING.iterdir()):
        if not d.is_dir():
            continue
        p = d / f"{d.name}.json"
        if p.exists():
            j = json.loads(p.read_text())
            g = j.get("grade") or {}
            rows.append((
                d.name, "pending_remediation", g.get("letter"), g.get("score"), g.get("verdict"),
                j.get("ocsf", {}).get("class_uid"), g.get("required_field_coverage_pct", 0),
            ))
    rows.sort(key=lambda r: (status_sort_key(r[1]), -(r[3] or 0)))

    emoji_map = {"A": "A", "B": "B", "C": "C", "D": "D", "F": "F"}

    lines = [
        "# Transform Grades — All 132",
        "",
        "Harness grade comes from the 5-module Purple-Pipeline-Parser-Eater harness: Lua validity, lint, OCSF mapping, field coverage, execution.",
        "Orion verdict is an independent AI review cross-check.",
        "",
        "| Transform | Status | Grade | Score | Orion verdict | OCSF class | Req field cov |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, status, letter, score, verdict, class_uid, req_cov in rows:
        tag = emoji_map.get(letter, "-")
        lines.append(
            f"| `{name}` | {status} | **{tag}** | {score if score is not None else '-'} | "
            f"`{verdict if verdict else '-'}` | {class_uid if class_uid else 'n/a'} | {req_cov}% |"
        )
    (BUNDLE / "GRADES.md").write_text("\n".join(lines) + "\n")
    return len(rows)


def update_top_readme():
    existing = (BUNDLE / "README.md").read_text()
    marker = "## Validation"
    grade_section = """## Grades

Every transform exposes a harness grade as a top-level field in both `<transform>.json` and `metadata.yaml`:

```json
{
  "grade": {
    "letter": "B",
    "score": 85,
    "verdict": "signed_off",
    "required_field_coverage_pct": 100,
    "source_field_coverage_pct": 100,
    "tested_with_realistic_event": true,
    "validated_at": "2026-04-19"
  }
}
```

See **[GRADES.md](GRADES.md)** for a one-table overview of every transform's grade, Orion verdict, and OCSF class.

## Validation"""
    if marker in existing and "## Grades" not in existing:
        existing = existing.replace(marker, grade_section)
        (BUNDLE / "README.md").write_text(existing)


def rezip():
    import zipfile

    out = Path("output/transform_ocsf_bundle_v4.zip")
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in BUNDLE.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(BUNDLE.parent))
    return out


if __name__ == "__main__":
    n = promote_all()
    print(f"Promoted grade in {n} transforms")
    n = write_remediations()
    print(f"Wrote {n} REMEDIATION.md files")
    write_pending_readme()
    print("Updated _pending_remediation/README.md")
    n = build_grades_md()
    print(f"GRADES.md: {n} rows")
    update_top_readme()
    print("Updated top-level README.md")
    out = rezip()
    print(f"Zipped: {out}  ({out.stat().st_size / 1024:.1f} KB)")
