# Purple Pipeline Parser Eater - Conversion Report

**Generated**: 2025-10-16 14:59:16
**Total Runtime**: 891.79 seconds (14.86 minutes)

## Executive Summary

- **Parsers Scanned**: 10
- **Parsers Analyzed**: 10
- **LUA Generated**: 10
- **Pipelines Deployed**: 0
- **GitHub Uploads**: 0
- **Errors**: 10

## Success Rates

- **Scan to Analysis**: 100.0%
- **Analysis to LUA**: 100.0%
- **LUA to Deployment**: 0.0%
- **Overall Success**: 0.0%

## Phase Timings

| Phase | Duration | Description |
|-------|----------|-------------|
| Phase 1 | 656.76s | Scanning parsers from GitHub |
| Phase 2 | 51.01s | Semantic analysis with Claude |
| Phase 3 | 165.79s | LUA code generation |
| Phase 4 | 18.23s | Deployment and GitHub upload |
| Phase 5 | 0.00s | Report generation |
| **Total** | **891.79s** | **Complete workflow** |

## Deployment Results


## Errors and Issues

- abnormal_security_logs-latest: Validated pipeline deployment failed: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]
- agent_metrics_logs-latest: Validated pipeline deployment failed: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]
- akamai_cdn-latest: Validated pipeline deployment failed: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]
- akamai_dns-latest: Validated pipeline deployment failed: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]
- akamai_general-latest: Validated pipeline deployment failed: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]
- akamai_sitedefender-latest: Validated pipeline deployment failed: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]
- apache_http_logs-latest: Validated pipeline deployment failed: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]
- armis_armis_logs-latest: Validated pipeline deployment failed: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]
- aruba_clearpass_logs-latest: Validated pipeline deployment failed: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]
- aws_cloudwatch_logs-latest: Validated pipeline deployment failed: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]


## Component Statistics

### GitHub Scanner
{
  "total_scanned": 161,
  "community_parsers": 144,
  "sentinelone_parsers": 17,
  "claude_json_fixes": 122,
  "claude_multipass_fixes": 0,
  "heuristic_fixes": 0,
  "errors": [],
  "scan_start": "2025-10-16T14:44:24.327229",
  "scan_end": "2025-10-16T14:55:21.057714",
  "mock_mode": false
}

### Claude Analyzer
{
  "total_analyzed": 10,
  "successful": 10,
  "failed": 0,
  "total_tokens_used": 22537,
  "errors": [],
  "success_rate": 1.0
}

### LUA Generator
{
  "total_generated": 10,
  "successful": 10,
  "failed": 0,
  "total_tokens_used": 52683,
  "errors": [],
  "success_rate": 1.0
}

### Observo Client
{
  "pipelines_created": 0,
  "deployments_successful": 0,
  "deployments_failed": 10,
  "errors": [
    "s1-abnormal_security_logs-latest: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]",
    "s1-agent_metrics_logs-latest: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]",
    "s1-akamai_cdn-latest: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]",
    "s1-akamai_dns-latest: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]",
    "s1-akamai_general-latest: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]",
    "s1-akamai_sitedefender-latest: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]",
    "s1-apache_http_logs-latest: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]",
    "s1-armis_armis_logs-latest: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]",
    "s1-aruba_clearpass_logs-latest: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]",
    "s1-aws_cloudwatch_logs-latest: HTTP error during deployment: Cannot connect to host api.observo.ai:443 ssl:default [getaddrinfo failed]"
  ],
  "rag_queries": 0,
  "optimization_applied": 0,
  "success_rate": 0.0
}

### GitHub Automation
{
  "files_uploaded": 0,
  "commits_created": 0,
  "errors": []
}

---
**Purple Pipeline Parser Eater v1.0.0**
