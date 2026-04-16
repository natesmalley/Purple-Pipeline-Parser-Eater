# API Reference

Complete REST API reference for Purple Pipeline Parser Eater 2.

All endpoints are served by the Flask web worker on port 8080. When `WEB_UI_AUTH_TOKEN` is set, every request must include the `X-Auth-Token` header.

---

## Table of Contents

- [Authentication](#authentication)
- [Health](#health)
- [Review Queue](#review-queue)
- [Workbench](#workbench)
- [Settings](#settings)
- [Runtime Status](#runtime-status)
- [Metrics](#metrics)
- [CSRF](#csrf)

---

## Authentication

When `WEB_UI_AUTH_TOKEN` is configured (required for non-loopback deployments), include the token in every request:

```http
X-Auth-Token: your-auth-token-here
```

For browser-based access, CSRF protection is enabled via Flask-WTF. Fetch a CSRF token from `GET /api/csrf-token` and include it in form submissions or as an `X-CSRFToken` header.

---

## Health

### GET /health

Health check endpoint used by Docker and load balancers.

**Response** `200 OK`:

```json
{
  "status": "healthy"
}
```

---

## Review Queue

Endpoints for managing the pending conversion review queue.

### GET /

Serves the main review UI (HTML page). Redirects to the review queue view.

### GET /workbench

Serves the workbench single-page application (HTML page).

### GET /api/v1/pending

Returns all pending conversions awaiting review.

**Response** `200 OK`:

```json
{
  "conversions": [
    {
      "parser_name": "okta_logs",
      "status": "pending",
      "score": 82,
      "created_at": "2026-04-15T10:30:00Z",
      "lua_preview": "function process(event, emit)..."
    }
  ],
  "total": 1
}
```

### GET /api/v1/conversion/\<parser_name\>

Returns details for a specific pending conversion.

**Path parameters:**

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `parser_name` | string | URL-encoded parser name |

**Response** `200 OK`:

```json
{
  "parser_name": "okta_logs",
  "status": "pending",
  "score": 82,
  "lua_code": "...",
  "harness_report": { "..." },
  "created_at": "2026-04-15T10:30:00Z"
}
```

### POST /api/v1/approve

Approve a pending conversion. Moves the Lua to `output/` and optionally triggers deploy.

**Request body:**

```json
{
  "parser_name": "okta_logs",
  "notes": "Looks good after manual review"
}
```

**Response** `200 OK`:

```json
{
  "status": "approved",
  "parser_name": "okta_logs"
}
```

### POST /api/v1/reject

Reject a pending conversion with a reason.

**Request body:**

```json
{
  "parser_name": "okta_logs",
  "reason": "Missing severity_id mapping"
}
```

**Response** `200 OK`:

```json
{
  "status": "rejected",
  "parser_name": "okta_logs"
}
```

### POST /api/v1/modify

Modify a pending conversion with updated Lua code.

**Request body:**

```json
{
  "parser_name": "okta_logs",
  "lua_code": "function process(event, emit)\n  ...\nend",
  "notes": "Fixed severity_id mapping"
}
```

**Response** `200 OK`:

```json
{
  "status": "modified",
  "parser_name": "okta_logs"
}
```

---

## Workbench

Endpoints for the parser conversion workbench.

### GET /api/v1/workbench/parsers

List available parsers for conversion.

**Response** `200 OK`:

```json
{
  "parsers": [
    {
      "name": "okta_logs",
      "vendor": "Okta",
      "product": "Identity Cloud",
      "type": "community"
    }
  ]
}
```

### POST /api/v1/workbench/build

Trigger Lua generation for a parser. This is a synchronous call that invokes the LLM.

**Request body:**

```json
{
  "parser_name": "okta_logs",
  "samples": [
    "{\"actor\":{\"displayName\":\"admin\"},\"eventType\":\"user.session.start\"}"
  ],
  "ocsf_version": "1.1.0"
}
```

**Response** `200 OK`:

```json
{
  "parser_name": "okta_logs",
  "lua_code": "-- OCSF Helper Functions\nlocal function setNestedField(...)\n...",
  "score": 85,
  "harness_report": {
    "checks": { "..." },
    "missing_fields": [],
    "lint_errors": []
  },
  "model_used": "claude-haiku-4-5-20251001",
  "generation_time_ms": 4523
}
```

### POST /api/v1/workbench/agent-build

Trigger iterative Lua generation with harness feedback loop and model escalation.

**Request body:** Same as `/workbench/build`.

**Response:** Same structure as `/workbench/build`, but may use a stronger model if the initial score was below 70.

### GET /api/v1/workbench/validate/\<parser_name\>

### POST /api/v1/workbench/validate/\<parser_name\>

Run the full 5-check harness against the current Lua for a parser.

**Path parameters:**

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `parser_name` | string | URL-encoded parser name |

**POST request body** (optional, to validate custom Lua):

```json
{
  "lua_code": "function process(event, emit)\n  ...\nend"
}
```

**Response** `200 OK`:

```json
{
  "parser_name": "okta_logs",
  "score": 85,
  "checks": {
    "lua_validity": { "passed": true },
    "lua_lint": { "passed": true, "warnings": [] },
    "ocsf_mapping": { "passed": true, "missing_fields": [] },
    "source_coverage": { "passed": false, "coverage_pct": 72, "missing": ["dst_endpoint.ip"] },
    "event_execution": { "passed": true, "events_tested": 4, "events_passed": 4 }
  }
}
```

### GET /api/v1/workbench/lint/\<parser_name\>

Run Lua linting only (faster than full validation, no event execution).

**Response** `200 OK`:

```json
{
  "parser_name": "okta_logs",
  "lint_passed": true,
  "errors": [],
  "warnings": []
}
```

### GET /api/v1/workbench/ocsf-mapping/\<parser_name\>

Get OCSF field mapping analysis for a parser.

**Response** `200 OK`:

```json
{
  "parser_name": "okta_logs",
  "ocsf_class": "Authentication",
  "class_uid": 3002,
  "required_fields": {
    "class_uid": { "present": true, "value": 3002 },
    "category_uid": { "present": true, "value": 3 },
    "activity_id": { "present": true },
    "time": { "present": true },
    "type_uid": { "present": true },
    "severity_id": { "present": true }
  },
  "mapped_fields": 24,
  "total_ocsf_fields": 31
}
```

### GET /api/v1/workbench/source-fields/\<parser_name\>

Get extracted source fields from the parser definition.

**Response** `200 OK`:

```json
{
  "parser_name": "okta_logs",
  "fields": ["actor.displayName", "eventType", "outcome.result", "client.ipAddress"]
}
```

### POST /api/v1/workbench/test-run/\<parser_name\>

Execute Lua against test events and return per-event results.

**Request body** (optional):

```json
{
  "lua_code": "function process(event, emit)...",
  "events": [
    { "actor": { "displayName": "admin" }, "eventType": "user.session.start" }
  ]
}
```

**Response** `200 OK`:

```json
{
  "parser_name": "okta_logs",
  "events_tested": 4,
  "events_passed": 3,
  "results": [
    {
      "event_index": 0,
      "passed": true,
      "input": { "..." },
      "output": { "..." },
      "ocsf_fields_present": ["class_uid", "category_uid", "time"]
    }
  ]
}
```

### POST /api/v1/workbench/execute

Execute arbitrary Lua against provided events (Playground endpoint).

**Request body:**

```json
{
  "lua_code": "function process(event, emit)\n  emit(event)\nend",
  "events": [
    { "message": "test event" }
  ]
}
```

**Response** `200 OK`:

```json
{
  "results": [
    {
      "event_index": 0,
      "success": true,
      "output": { "message": "test event" },
      "error": null
    }
  ]
}
```

### GET /api/v1/workbench/ocsf-versions

List available OCSF schema versions.

**Response** `200 OK`:

```json
{
  "versions": ["1.0.0", "1.1.0", "1.2.0"],
  "default": "1.1.0"
}
```

### POST /api/v1/workbench/jobs

Submit an async workbench job (build, validate, or test-run).

**Request body:**

```json
{
  "action": "build",
  "parser_name": "okta_logs",
  "samples": ["..."]
}
```

**Response** `202 Accepted`:

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued"
}
```

### GET /api/v1/workbench/jobs/\<job_id\>

Poll the status of an async job.

**Response** `200 OK`:

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "result": { "..." }
}
```

### POST /api/v1/workbench/match-feedback

Submit field mapping feedback for a parser.

**Request body:**

```json
{
  "parser_name": "okta_logs",
  "field_mappings": [
    {
      "source_field": "actor.displayName",
      "ocsf_field": "actor.user.name",
      "correct": true
    },
    {
      "source_field": "client.ipAddress",
      "ocsf_field": "src_endpoint.ip",
      "correct": false,
      "suggested_field": "actor.user.ip"
    }
  ]
}
```

**Response** `200 OK`:

```json
{
  "status": "recorded",
  "corrections_saved": 1
}
```

### POST /api/v1/workbench/save-correction

Save an inline Lua correction for future prompt enrichment.

**Request body:**

```json
{
  "parser_name": "okta_logs",
  "original_lua": "-- original code...",
  "corrected_lua": "-- fixed code...",
  "reason": "Fixed severity_id to use OCSF enum instead of raw string",
  "ocsf_class_uid": 3002
}
```

**Response** `200 OK`:

```json
{
  "status": "saved",
  "correction_id": "corr_20260415T103000_abc123"
}
```

### POST /api/v1/workbench/upload-pr

Upload approved Lua as a GitHub pull request.

**Request body:**

```json
{
  "parser_name": "okta_logs"
}
```

**Response** `200 OK`:

```json
{
  "status": "created",
  "pr_url": "https://github.com/your-org/observo-pipelines/pull/42"
}
```

### GET /api/v1/workbench/agent-cache-stats

Get cache statistics for the agentic Lua generator.

**Response** `200 OK`:

```json
{
  "cache_size": 12,
  "hit_rate": 0.75,
  "entries": [...]
}
```

### GET /api/v1/workbench/batch-status

Get the status of batch conversion operations.

**Response** `200 OK`:

```json
{
  "in_progress": false,
  "total_parsers": 0,
  "completed": 0,
  "failed": 0
}
```

---

## Settings

### GET /api/v1/settings

Retrieve current settings (secrets are redacted).

**Response** `200 OK`:

```json
{
  "providers": {
    "active": "anthropic",
    "anthropic": {
      "api_key": "****k3Xy",
      "model": "claude-haiku-4-5-20251001",
      "strong_model": "claude-sonnet-4-6"
    },
    "openai": {
      "api_key": "",
      "model": "gpt-5.4-mini",
      "strong_model": "gpt-5.4"
    },
    "gemini": {
      "api_key": "",
      "model": "gemini-3.1-flash-lite",
      "strong_model": "gemini-3.1-pro"
    }
  },
  "tuning": {
    "llm_max_tokens": 3000,
    "llm_max_iterations": 2,
    "anthropic_temperature": 0
  },
  "integrations": {
    "github": { "token": "****ab12", "owner": "your-org", "repo": "observo-pipelines" },
    "observo": { "api_key": "", "base_url": "https://api.observo.ai/v1" }
  },
  "rag": { "enabled": true }
}
```

### POST /api/v1/settings

Update settings. Partial updates are supported -- only include fields you want to change.

**Request body:**

```json
{
  "providers": {
    "active": "openai",
    "openai": {
      "api_key": "sk-your-openai-key-here"
    }
  },
  "tuning": {
    "llm_max_tokens": 4000
  }
}
```

**Response** `200 OK`:

```json
{
  "status": "saved",
  "restart_required": false
}
```

If `restart_required` is `true`, the worker must be restarted for the change to take effect.

### POST /api/v1/settings/test/\<provider\>

Test connectivity to an LLM provider.

**Path parameters:**

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `provider` | string | `anthropic`, `openai`, or `gemini` |

**Request body** (optional -- uses stored key if omitted):

```json
{
  "api_key": "sk-ant-your-key-here"
}
```

**Response** `200 OK`:

```json
{
  "status": "success",
  "provider": "anthropic",
  "model": "claude-haiku-4-5-20251001",
  "response_time_ms": 342
}
```

**Response** `400 Bad Request`:

```json
{
  "status": "error",
  "provider": "anthropic",
  "error": "Invalid API key"
}
```

### POST /api/v1/settings/restart-worker

Request a restart of the conversion worker process.

**Response** `200 OK`:

```json
{
  "status": "restart_requested"
}
```

---

## Runtime Status

### GET /api/v1/status

Get high-level application status.

**Response** `200 OK`:

```json
{
  "status": "running",
  "uptime_seconds": 3600,
  "pending_conversions": 3
}
```

### GET /api/v1/runtime/status

Get detailed conversion worker runtime status (reads from RuntimeProxy).

**Response** `200 OK`:

```json
{
  "worker_status": "idle",
  "last_conversion": "2026-04-15T10:25:00Z",
  "github_sync_last_run": "2026-04-15T09:30:00Z",
  "feedback_drain_last_run": "2026-04-15T10:28:00Z"
}
```

### POST /api/v1/runtime/reload/\<parser_id\>

Request a reload of a specific parser in the runtime.

### DELETE /api/v1/runtime/reload/\<parser_id\>

Cancel a pending reload request.

### POST /api/v1/runtime/canary/\<parser_id\>/promote

Promote a canary deployment for a parser.

### DELETE /api/v1/runtime/canary/\<parser_id\>/promote

Cancel a canary promotion.

---

## Metrics

### GET /api/v1/metrics

Prometheus-format metrics endpoint.

**Response** `200 OK` (text/plain):

```text
# HELP pppe_conversions_total Total conversions attempted
# TYPE pppe_conversions_total counter
pppe_conversions_total{status="success"} 42
pppe_conversions_total{status="failed"} 3
# HELP pppe_harness_score_histogram Harness score distribution
# TYPE pppe_harness_score_histogram histogram
pppe_harness_score_histogram_bucket{le="50"} 2
pppe_harness_score_histogram_bucket{le="70"} 5
pppe_harness_score_histogram_bucket{le="90"} 35
pppe_harness_score_histogram_bucket{le="100"} 42
```

---

## CSRF

### GET /api/csrf-token

Fetch a CSRF token for form submissions.

**Response** `200 OK`:

```json
{
  "csrf_token": "IjY3YzU..."
}
```

Include this token in form submissions as a hidden field or as the `X-CSRFToken` request header.

---

## Error Responses

All endpoints return errors in a consistent format:

```json
{
  "error": "Parser not found",
  "detail": "No conversion exists for parser 'nonexistent_parser'",
  "status": 404
}
```

Common status codes:

| Code | Meaning |
| ---- | ------- |
| 400 | Bad request (invalid input, failed validation) |
| 401 | Unauthorized (missing or invalid `X-Auth-Token`) |
| 403 | Forbidden (CSRF token mismatch) |
| 404 | Resource not found |
| 429 | Rate limited (Flask-Limiter) |
| 500 | Internal server error |
