# Data Flow Diagrams (DFD)

## Purple Pipeline Parser Eater v9.0.0

**Document Classification**: Internal Use Only
**Last Updated**: 2025-10-10
**Version**: 1.0
**Purpose**: Visual representation of data flows, trust boundaries, and security controls

---

## Table of Contents

1. [Context Diagram (Level 0)](#1-context-diagram-level-0)
2. [System Diagram (Level 1)](#2-system-diagram-level-1)
3. [Component Diagram (Level 2)](#3-component-diagram-level-2)
4. [Detailed Flow Diagrams](#4-detailed-flow-diagrams)
5. [Trust Boundary Analysis](#5-trust-boundary-analysis)
6. [Data Classification Flow](#6-data-classification-flow)

---

## 1. Context Diagram (Level 0)

### 1.1 System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTEXT DIAGRAM (LEVEL 0)                     │
│            Purple Pipeline Parser Eater - System Context         │
└─────────────────────────────────────────────────────────────────┘

                    ┌───────────────────┐
                    │   Human User      │
                    │   (Analyst/       │
                    │    Developer)     │
                    └─────────┬─────────┘
                              │
                              │ [1] Parser Description
                              │ (HTTPS, User Input)
                              │
                              ▼
        ┌───────────────────────────────────────────┐
        │                                           │
        │    Purple Pipeline Parser Eater          │
        │    ─────────────────────────────────────│
        │    • Parse user input                    │
        │    • Generate Lua pipeline               │
        │    • Validate output                     │
        │    • Provide feedback loop               │
        │                                           │
        └───────────────────────────────────────────┘
           │           │            │            │
           │[2]        │[3]         │[4]         │[5]
           │           │            │            │
┌──────────▼─────┐ ┌──▼──────┐ ┌───▼────────┐ ┌─▼────────────┐
│  Anthropic     │ │SentinelOne│ │ Observo.ai │ │   AWS        │
│  Claude API    │ │  Purple   │ │  Platform  │ │  Services    │
│  ────────────  │ │    AI     │ │ ──────────│ │  ──────────  │
│  • Generate    │ │  ────────│ │  • Deploy  │ │  • Secrets   │
│    code        │ │  • Threat │ │    pipeline│ │  • Logs      │
│  • Refine      │ │    intel  │ │  • Test    │ │  • KMS       │
│    output      │ │  • Context│ │    parser  │ └──────────────┘
└────────────────┘ └───────────┘ └────────────┘
         ▲                                │
         │                                │
         └────────[6] GitHub Docs─────────┘
                 (RAG Context)


Data Flow Legend:
─────────────────
[1] User Input: Parser description, natural language (CONFIDENTIAL)
[2] AI Request: User prompt + context (INTERNAL, encrypted TLS 1.2+)
[3] Threat Intel: Query context (INTERNAL, encrypted TLS 1.2+)
[4] Pipeline Deploy: Lua code + metadata (INTERNAL, encrypted TLS 1.2+)
[5] Support Services: Secrets, logs, encryption keys (CONFIDENTIAL)
[6] Documentation: Public GitHub repos (PUBLIC, but rate-limited)

Trust Boundaries:
─────────────────
• Internet → System: TLS 1.2+, WAF, authentication
• System → External APIs: TLS 1.2+, API keys (AWS Secrets Manager)
• System → AWS: IAM roles, VPC endpoints
```

### 1.2 External Entities

| Entity | Type | Data Sent | Data Received | Security |
|--------|------|-----------|---------------|----------|
| **Human User** | Person | Parser descriptions, feedback | Generated pipelines, status | HTTPS, session cookies |
| **Anthropic Claude** | External System | User prompts, context | Generated Lua code | TLS 1.2+, API key |
| **SentinelOne** | External System | Query requests | Threat intelligence | TLS 1.2+, API key |
| **Observo.ai** | External System | Lua pipelines | Deployment status | TLS 1.2+, API key |
| **AWS Services** | External System | Log data, secret requests | Secrets, encryption keys | IAM, VPC endpoints |
| **GitHub** | External System | API requests | Documentation markdown | TLS 1.2+, API key (rate limit) |

---

## 2. System Diagram (Level 1)

### 2.1 High-Level System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYSTEM DIAGRAM (LEVEL 1)                      │
│            Purple Pipeline Parser Eater - Components             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Trust Boundary: INTERNET (Untrusted)                           │
│                                                                   │
│         [User Browser] ──────HTTPS (TLS 1.2+)──────▶            │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                                    │ [1.1] HTTPS Request
                                    │      + User Input
                                    │
┌───────────────────────────────────▼─────────────────────────────┐
│  Trust Boundary: DMZ (Semi-Trusted)                             │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  [1.0] Perimeter Security                                  │ │
│  │  • AWS WAF (rate limiting, OWASP rules)                    │ │
│  │  • ALB (TLS termination, health checks)                    │ │
│  │  • DDoS Protection (AWS Shield)                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              │ [1.2] Validated Request          │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  [2.0] Ingress Controller                                  │ │
│  │  • NGINX Ingress (routing, SSL)                            │ │
│  │  • cert-manager (certificate management)                   │ │
│  │  • Rate limiting per endpoint                              │ │
│  └────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┬─┘
                                    │
                                    │ [1.3] Routed Request
                                    │
┌───────────────────────────────────▼─────────────────────────────┐
│  Trust Boundary: APPLICATION (Kubernetes - Trusted)             │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  [3.0] Orchestrator                                        │ │
│  │  ──────────────────────────────────────────────────────────│ │
│  │  Input: User description, config                           │ │
│  │  • Route requests to appropriate service                   │ │
│  │  • Expand environment variables                            │ │
│  │  • Load configuration                                      │ │
│  │  Output: Processed request                                 │ │
│  └─┬────────────────────────────────────────────────┬─────────┘ │
│    │                                                 │           │
│    │ [3.1] Main Flow                                 │ [3.2]     │
│    │                                         Continuous Flow    │
│    ▼                                                 ▼           │
│  ┌──────────────────────────────┐  ┌──────────────────────────┐│
│  │ [4.0] Main Parser Generator  │  │ [5.0] Continuous Service ││
│  │ ────────────────────────────│  │ ──────────────────────── ││
│  │ • Validate input             │  │ • Queue processing       ││
│  │ • Call Claude API            │  │ • Batch generation       ││
│  │ • Parse response             │  │ • Auto-deployment        ││
│  │ • Validate Lua code          │  │ • Error handling         ││
│  └──────────────┬───────────────┘  └──────────┬───────────────┘│
│                 │                              │                 │
│                 │ [4.1] Lua Code               │                 │
│                 │                              │                 │
│                 ▼                              │                 │
│  ┌────────────────────────────────────────────▼───────────────┐ │
│  │ [6.0] Pipeline Validator                                   │ │
│  │ ──────────────────────────────────────────────────────────│ │
│  │ • Syntax validation                                        │ │
│  │ • Security checks (injection prevention)                  │ │
│  │ • Observo.ai compatibility check                          │ │
│  │ • Pattern matching validation                             │ │
│  └────────────────────────────────┬────────────────────────────┘ │
│                                   │                              │
│                                   │ [6.1] Validated Pipeline     │
│                                   ▼                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ [7.0] Parser Output Manager                                │ │
│  │ ──────────────────────────────────────────────────────────│ │
│  │ • Write to encrypted storage                               │ │
│  │ • Generate metadata                                        │ │
│  │ • Track versions                                           │ │
│  │ • Queue for feedback                                       │ │
│  └──────────────┬───────────────────────────────┬─────────────┘ │
│                 │                               │                │
│                 │ [7.1] Store                   │ [7.2] Feedback │
│                 ▼                               ▼                │
│  ┌──────────────────────┐      ┌──────────────────────────────┐ │
│  │ [8.0] EBS Storage    │      │ [9.0] Web Feedback UI        │ │
│  │ ────────────────────│      │ ──────────────────────────── │ │
│  │ • Encrypted volumes  │      │ • Flask web server           │ │
│  │ • 30-day retention   │      │ • CSRF protection            │ │
│  │ • Path validation    │      │ • XSS prevention             │ │
│  └──────────────────────┘      │ • Session management         │ │
│                                 │ • Approve/Reject workflow    │ │
│                                 └──────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ [10.0] Supporting Services                                 │ │
│  │ ──────────────────────────────────────────────────────────│ │
│  │ • RAG Auto Updater (GitHub docs ingestion)                 │ │
│  │ • Security Logging (CloudWatch integration)                │ │
│  │ • File Integrity Monitoring (AIDE)                         │ │
│  │ • Vulnerability Scanner (Trivy)                            │ │
│  └────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┬─┘
                                    │
                                    │ [11] External API Calls
                                    │      (TLS 1.2+, API Keys)
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Trust Boundary: EXTERNAL SERVICES (Verified Partners)          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Anthropic   │  │ SentinelOne  │  │  Observo.ai  │         │
│  │  Claude API  │  │   Purple AI  │  │   Platform   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    │ [12] Support Services
                                    │      (IAM, VPC Endpoints)
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Trust Boundary: AWS SERVICES (Managed, High Trust)             │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Secrets    │  │  CloudWatch  │  │     KMS      │         │
│  │   Manager    │  │    Logs      │  │ (Encryption) │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Store Inventory

| ID | Data Store | Type | Data Classification | Encryption | Retention |
|----|----------|------|---------------------|------------|-----------|
| **8.0** | EBS Volumes | Block storage | INTERNAL | AES-256 (KMS) | 30 days |
| **AWS-1** | AWS Secrets Manager | Key-value | CONFIDENTIAL | AES-256 (KMS) | Until rotated |
| **AWS-2** | CloudWatch Logs | Time-series | INTERNAL | AES-256 (KMS) | 90 days |
| **AWS-3** | S3 (logs archive) | Object storage | INTERNAL | AES-256 (KMS) | 7 years |
| **K8s-1** | ConfigMaps | Key-value | INTERNAL | Not encrypted | Indefinite |
| **K8s-2** | Secrets (K8s) | Key-value | CONFIDENTIAL | Base64 (not encrypted) | Indefinite |

**Security Note**: Kubernetes Secrets are NOT encrypted at rest by default. We use AWS Secrets Manager with External Secrets Operator for actual secret storage.

---

## 3. Component Diagram (Level 2)

### 3.1 Main Parser Generator (Detailed)

```
┌─────────────────────────────────────────────────────────────────┐
│          COMPONENT DIAGRAM (LEVEL 2) - Main Parser Generator    │
└─────────────────────────────────────────────────────────────────┘

         [Orchestrator]
               │
               │ [A] User Description
               │     + Configuration
               ▼
┌────────────────────────────────────────────────────────────────┐
│  main.py - Main Parser Generator                               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [Step 1] Input Processing                               │  │
│  │  ────────────────────────────────────────────────────────│  │
│  │  def process_input(description: str) -> ProcessedInput:  │  │
│  │      • Trim whitespace                                   │  │
│  │      • Validate length (max 10KB)                        │  │
│  │      • Check for malicious patterns                      │  │
│  │      • Sanitize special characters                       │  │
│  │      return ProcessedInput(sanitized_description)        │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                        │
│                         │ [B] Sanitized Description             │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [Step 2] Context Enrichment                             │  │
│  │  ────────────────────────────────────────────────────────│  │
│  │  def enrich_context(input: ProcessedInput) -> Context:   │  │
│  │      • Load RAG documentation (ChromaDB)                 │  │
│  │      • Load example parsers (template library)           │  │
│  │      • Load Observo.ai Lua API reference                 │  │
│  │      • Build system prompt with context                  │  │
│  │      return Context(prompt, examples, docs)              │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                        │
│                         │ [C] Enriched Context                  │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [Step 3] Secrets Retrieval                              │  │
│  │  ────────────────────────────────────────────────────────│  │
│  │  def get_api_key() -> str:                               │  │
│  │      secrets = AWSSecretsManager()                       │  │
│  │      api_key = secrets.get_secret_value(                 │  │
│  │          'purple-parser/prod/anthropic-api-key',         │  │
│  │          'api_key'                                       │  │
│  │      )                                                    │  │
│  │      # Cache for 5 minutes                               │  │
│  │      return api_key                                      │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                        │
│                         │ [D] API Key (CONFIDENTIAL)            │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [Step 4] Claude API Call                                │  │
│  │  ────────────────────────────────────────────────────────│  │
│  │  def call_claude_api(context: Context) -> LuaCode:       │  │
│  │      client = anthropic.Anthropic(api_key=api_key)       │  │
│  │      message = client.messages.create(                   │  │
│  │          model="claude-3-5-sonnet-20241022",             │  │
│  │          messages=[{"role": "user", "content": prompt}]  │  │
│  │      )                                                    │  │
│  │      lua_code = extract_lua_code(message.content)        │  │
│  │      # Log request (redact API key)                      │  │
│  │      logger.info("claude_api_call", request_id=...)      │  │
│  │      return lua_code                                     │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                        │
│                         │ [E] Raw Lua Code                      │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [Step 5] Lua Code Extraction                            │  │
│  │  ────────────────────────────────────────────────────────│  │
│  │  def extract_lua_code(response: str) -> str:             │  │
│  │      • Parse markdown code blocks                        │  │
│  │      • Validate Lua syntax (lupa.LuaRuntime)             │  │
│  │      • Remove comments and debug statements              │  │
│  │      • Normalize whitespace                              │  │
│  │      return clean_lua_code                               │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                        │
│                         │ [F] Extracted Lua Code                │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [Step 6] Send to Validator                              │  │
│  │  ────────────────────────────────────────────────────────│  │
│  │  validator = PipelineValidator()                         │  │
│  │  result = validator.validate(lua_code)                   │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                        │
└─────────────────────────┼────────────────────────────────────────┘
                          │ [G] Validation Request
                          ▼
                [Pipeline Validator]
                          │
                          │ [H] Validation Result
                          │     (Valid/Invalid + Errors)
                          ▼
                [Parser Output Manager]


Data Flow Security:
────────────────────
[A] User Description: XSS sanitization, length validation
[B] Sanitized: Path traversal prevention, command injection checks
[C] Context: Internal data only, no secrets
[D] API Key: Retrieved from AWS Secrets Manager (encrypted), never logged
[E] Raw Lua: May contain Claude hallucinations or errors
[F] Extracted: Clean Lua code, syntax-validated
[G] Validation Request: Pass to validator component
[H] Validation Result: Boolean + error list

Logging & Monitoring:
──────────────────────
• [Step 1]: Log input length, sanitization actions
• [Step 2]: Log RAG retrieval time, context size
• [Step 3]: Log secret retrieval (NOT the secret value)
• [Step 4]: Log API call (request_id, latency, status)
• [Step 5]: Log extraction success/failure
• [Step 6]: Log validation result

Error Handling:
────────────────
• Invalid input → Return 400 error to user
• API key retrieval failure → Return 500 error, alert security team
• Claude API failure → Retry 3x with exponential backoff
• Validation failure → Return error details to user for refinement
```

### 3.2 Pipeline Validator (Detailed)

```
┌─────────────────────────────────────────────────────────────────┐
│          COMPONENT DIAGRAM (LEVEL 2) - Pipeline Validator       │
└─────────────────────────────────────────────────────────────────┘

         [Main Parser Generator]
                    │
                    │ [G] Lua Code String
                    ▼
┌────────────────────────────────────────────────────────────────┐
│  pipeline_validator.py - Pipeline Validator                     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [Check 1] Syntax Validation                             │  │
│  │  ────────────────────────────────────────────────────────│  │
│  │  def validate_syntax(lua_code: str) -> ValidationResult: │  │
│  │      try:                                                │  │
│  │          lua = lupa.LuaRuntime()                         │  │
│  │          # Compile Lua code (don't execute)              │  │
│  │          lua.eval(f"function() {lua_code} end")          │  │
│  │          return ValidationResult(valid=True)             │  │
│  │      except lupa.LuaSyntaxError as e:                    │  │
│  │          return ValidationResult(                        │  │
│  │              valid=False,                                │  │
│  │              error=f"Syntax error: {e}"                  │  │
│  │          )                                               │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                        │
│                         │ [1.1] Syntax Valid                    │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [Check 2] Security Validation                           │  │
│  │  ────────────────────────────────────────────────────────│  │
│  │  def validate_security(lua_code: str) -> SecurityResult: │  │
│  │      dangerous_patterns = [                              │  │
│  │          r'os\.execute',     # Command injection         │  │
│  │          r'io\.popen',       # Command injection         │  │
│  │          r'loadstring',      # Code injection            │  │
│  │          r'dofile',          # File access               │  │
│  │          r'require\s*\(',    # Module loading            │  │
│  │          r'\.\.\/',          # Path traversal            │  │
│  │      ]                                                   │  │
│  │      for pattern in dangerous_patterns:                  │  │
│  │          if re.search(pattern, lua_code):                │  │
│  │              logger.warning(                             │  │
│  │                  "security_violation",                   │  │
│  │                  pattern=pattern,                        │  │
│  │                  code_snippet=lua_code[:100]             │  │
│  │              )                                           │  │
│  │              return SecurityResult(                      │  │
│  │                  valid=False,                            │  │
│  │                  violation=f"Dangerous: {pattern}"       │  │
│  │              )                                           │  │
│  │      return SecurityResult(valid=True)                   │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                        │
│                         │ [2.1] Security Valid                  │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [Check 3] Observo.ai API Compatibility                  │  │
│  │  ────────────────────────────────────────────────────────│  │
│  │  def validate_observo_api(lua_code: str) -> ApiResult:   │  │
│  │      # Check required functions exist                    │  │
│  │      required_functions = [                              │  │
│  │          'function parse(log)',                          │  │
│  │          'return'                                        │  │
│  │      ]                                                   │  │
│  │      for func in required_functions:                     │  │
│  │          if func not in lua_code:                        │  │
│  │              return ApiResult(                           │  │
│  │                  valid=False,                            │  │
│  │                  error=f"Missing: {func}"                │  │
│  │              )                                           │  │
│  │                                                          │  │
│  │      # Check for valid Observo.ai API calls              │  │
│  │      valid_api_calls = [                                 │  │
│  │          'o\.extract_regex', 'o\.parse_json',            │  │
│  │          'o\.parse_kv', 'o\.parse_csv', 'o\.grok'        │  │
│  │      ]                                                   │  │
│  │      # At least one API call should exist                │  │
│  │      has_api_call = any(                                 │  │
│  │          re.search(api, lua_code)                        │  │
│  │          for api in valid_api_calls                      │  │
│  │      )                                                   │  │
│  │      if not has_api_call:                                │  │
│  │          return ApiResult(                               │  │
│  │              valid=False,                                │  │
│  │              warning="No Observo.ai API calls found"     │  │
│  │          )                                               │  │
│  │      return ApiResult(valid=True)                        │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                        │
│                         │ [3.1] API Compatible                  │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [Check 4] Pattern Quality Check                         │  │
│  │  ────────────────────────────────────────────────────────│  │
│  │  def validate_patterns(lua_code: str) -> PatternResult:  │  │
│  │      # Extract regex patterns                            │  │
│  │      patterns = re.findall(                              │  │
│  │          r'["\']([^"\']*\\[^"\']*)["\']',                │  │
│  │          lua_code                                        │  │
│  │      )                                                   │  │
│  │      for pattern in patterns:                            │  │
│  │          try:                                            │  │
│  │              re.compile(pattern)                         │  │
│  │          except re.error as e:                           │  │
│  │              return PatternResult(                       │  │
│  │                  valid=False,                            │  │
│  │                  error=f"Invalid regex: {pattern}"       │  │
│  │              )                                           │  │
│  │      return PatternResult(valid=True)                    │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                        │
│                         │ [4.1] Patterns Valid                  │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [Final] Aggregate Results                               │  │
│  │  ────────────────────────────────────────────────────────│  │
│  │  def aggregate_validation() -> FinalValidationResult:    │  │
│  │      if all_checks_passed:                               │  │
│  │          logger.info("validation_success", code_hash=...) │  │
│  │          return FinalValidationResult(                   │  │
│  │              valid=True,                                 │  │
│  │              message="All validations passed"            │  │
│  │          )                                               │  │
│  │      else:                                               │  │
│  │          logger.warning("validation_failure", errors=...) │  │
│  │          return FinalValidationResult(                   │  │
│  │              valid=False,                                │  │
│  │              errors=[check1_error, check2_error, ...]    │  │
│  │          )                                               │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                        │
└─────────────────────────┼────────────────────────────────────────┘
                          │ [H] Final Validation Result
                          ▼
                [Parser Output Manager]


Validation Sequence:
─────────────────────
1. Syntax Validation (MANDATORY) - Blocks invalid Lua
2. Security Validation (MANDATORY) - Blocks dangerous code
3. API Compatibility (MANDATORY) - Blocks incompatible code
4. Pattern Quality (WARNING) - Alerts on regex issues

Blocked Patterns (Security):
─────────────────────────────
• os.execute() - Command injection
• io.popen() - Command injection
• loadstring() - Code injection
• dofile() - File system access
• require() - Module loading
• ../ - Path traversal

Logging & Alerting:
────────────────────
• Valid code: INFO level log
• Invalid syntax: WARNING level log
• Security violation: CRITICAL level log + alert to security team
• Pattern issues: WARNING level log
```

---

## 4. Detailed Flow Diagrams

### 4.1 User Request Flow (End-to-End)

```
┌─────────────────────────────────────────────────────────────────┐
│                  USER REQUEST FLOW (END-TO-END)                  │
│              Complete Flow from User to Pipeline Deployment      │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐
│ User Browser │
└──────┬───────┘
       │
       │ [1] POST /api/generate
       │     Body: {"description": "Parse Sysmon Event 1"}
       │     Headers: Cookie: session_id=abc123
       │     Protocol: HTTPS (TLS 1.2+)
       ▼
┌─────────────────────────────────────┐
│ AWS ALB (Trust Boundary 1)          │
│ • TLS termination                   │
│ • WAF inspection (OWASP rules)      │
│ • Rate limiting check               │
│ • Security headers injection        │
└──────┬──────────────────────────────┘
       │ [2] Validated Request
       │     X-Forwarded-For: 203.0.113.1
       │     X-Request-ID: req-789xyz
       ▼
┌─────────────────────────────────────┐
│ NGINX Ingress Controller            │
│ (Trust Boundary 2)                  │
│ • Certificate validation            │
│ • Endpoint rate limiting            │
│ • Request size check (max 10MB)     │
│ • Routing to service                │
└──────┬──────────────────────────────┘
       │ [3] Routed Request
       │     Service: purple-parser:8080
       ▼
┌─────────────────────────────────────┐
│ Kubernetes Service (ClusterIP)      │
│ • Load balancing to pods            │
│ • Health check enforcement          │
│ • Network policy check              │
└──────┬──────────────────────────────┘
       │ [4] Load-balanced Request
       │     Target Pod: purple-parser-0
       ▼
┌─────────────────────────────────────┐
│ Purple Parser Pod                   │
│ (Trust Boundary 3 - Application)    │
│ • Seccomp profile active            │
│ • AppArmor profile enforced         │
│ • Running as UID 1001 (non-root)    │
│ • Read-only root filesystem         │
└──────┬──────────────────────────────┘
       │ [5] Application Entry Point
       │     orchestrator.py
       ▼
┌─────────────────────────────────────┐
│ [5.1] Orchestrator                  │
│ • Parse request body                │
│ • Validate session cookie           │
│ • Extract user description          │
│ • Load configuration                │
│ • Route to main.py                  │
└──────┬──────────────────────────────┘
       │ [6] Orchestrated Request
       ▼
┌─────────────────────────────────────┐
│ [6.1] Main Parser Generator         │
│ Step 1: Input Validation            │
│   • Length check (max 10KB)         │
│   • XSS sanitization                │
│   • Command injection check         │
│   • Path traversal prevention       │
│                                     │
│ Step 2: Context Enrichment          │
│   • Load RAG docs (ChromaDB)        │
│   • Load example parsers            │
│   • Build system prompt             │
│                                     │
│ Step 3: Retrieve API Key            │
│   ├─[HTTPS]─▶ AWS Secrets Manager  │
│   │           • IAM role auth       │
│   │           • KMS decrypt         │
│   ├─[KEY]◀─── Return API key        │
│   └─ Cache key (5 min TTL)          │
│                                     │
│ Step 4: Call Claude API             │
│   ├─[HTTPS]─▶ api.anthropic.com    │
│   │           • TLS 1.2+ only       │
│   │           • API key in header   │
│   │           • Send enriched prompt│
│   ├─[JSON]◀── Lua code response     │
│   └─ Log request (redact API key)   │
│                                     │
│ Step 5: Extract Lua Code            │
│   • Parse markdown                  │
│   • Extract code blocks             │
│   • Basic syntax check              │
└──────┬──────────────────────────────┘
       │ [7] Lua Code String
       ▼
┌─────────────────────────────────────┐
│ [7.1] Pipeline Validator            │
│ Check 1: Syntax                     │
│   • lupa.LuaRuntime compile         │
│   • Catch syntax errors             │
│                                     │
│ Check 2: Security                   │
│   • Scan for os.execute()           │
│   • Scan for io.popen()             │
│   • Scan for loadstring()           │
│   • Block if violations found       │
│                                     │
│ Check 3: API Compatibility          │
│   • Check function parse(log)       │
│   • Verify Observo.ai API calls     │
│                                     │
│ Check 4: Pattern Quality            │
│   • Validate regex patterns         │
│   • Warn on invalid patterns        │
└──────┬──────────────────────────────┘
       │
       ├─[IF INVALID]─▶ Return 400 error with details
       │
       │ [8] Validated Lua Code
       ▼
┌─────────────────────────────────────┐
│ [8.1] Parser Output Manager         │
│ • Generate parser ID (UUID)         │
│ • Hash code (SHA-256)               │
│ • Write to EBS volume               │
│   └─ Path: /app/output/{id}.lua    │
│   └─ Encryption: AES-256 (KMS)      │
│ • Generate metadata JSON            │
│ • Queue for web feedback UI         │
│ • Log success event                 │
└──────┬──────────────────────────────┘
       │ [9] Parser ID + Path
       ▼
┌─────────────────────────────────────┐
│ [9.1] Web Feedback UI               │
│ • Add to feedback queue             │
│ • Generate approve/reject links     │
│ • Create CSRF tokens                │
│ • Return status to user             │
└──────┬──────────────────────────────┘
       │ [10] Response JSON
       │      {
       │        "status": "success",
       │        "parser_id": "uuid-123",
       │        "feedback_url": "/feedback/uuid-123"
       │      }
       ▼
┌─────────────────────────────────────┐
│ [10.1] Return to User               │
│ • HTTP 200 OK                       │
│ • Security headers                  │
│   └─ Content-Security-Policy        │
│   └─ X-Content-Type-Options         │
│   └─ X-Frame-Options                │
│ • HSTS header                       │
│ • Response body (JSON)              │
└──────┬──────────────────────────────┘
       │ [11] HTTPS Response (TLS 1.2+)
       ▼
┌──────────────┐
│ User Browser │
│ • Display    │
│   result     │
│ • Show       │
│   feedback   │
│   link       │
└──────────────┘


Parallel Flows:
────────────────
While the above flow is happening:

[Logging Flow]
  Application ──▶ Fluentd ──▶ CloudWatch Logs (encrypted)
  • All steps logged with request_id
  • Security events flagged
  • API keys redacted from logs

[Monitoring Flow]
  Application ──▶ CloudWatch Metrics
  • Request count
  • Latency
  • Error rate
  • API call duration

[Security Monitoring]
  Application ──▶ Security Event Logger ──▶ CloudWatch Alarms
  • Authentication failures
  • Validation failures
  • API errors
  • CSRF token mismatches


Timing (Typical):
──────────────────
[1] User request: 0ms
[2-4] Network routing: 10-20ms
[5-6] Orchestration: 5-10ms
[7] API key retrieval: 50-100ms (first time), 1ms (cached)
[8] Claude API call: 2000-5000ms (dominant)
[9] Validation: 50-100ms
[10] File write: 10-20ms
[11] Response: 10-20ms

Total: ~2.5-5.5 seconds (mostly Claude API)
```

### 4.2 Secrets Retrieval Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECRETS RETRIEVAL FLOW                        │
│              AWS Secrets Manager Integration                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Application Code (main.py)          │
│                                     │
│ from utils.aws_secrets_manager import get_secrets_manager      │
│                                     │
│ secrets = get_secrets_manager()     │
│ api_key = secrets.get_secret_value( │
│     'purple-parser/prod/anthropic', │
│     'api_key'                       │
│ )                                   │
└──────┬──────────────────────────────┘
       │
       │ [1] Check Local Cache
       │     (5-minute TTL)
       ▼
┌─────────────────────────────────────┐
│ AWSSecretsManager Class              │
│ • Cache lookup by secret name       │
│ • Check timestamp < cache_ttl       │
└──────┬──────────────────────────────┘
       │
       ├─[Cache HIT]─▶ Return cached value (instant)
       │
       │ [2] Cache MISS
       │     Fetch from AWS
       ▼
┌─────────────────────────────────────┐
│ boto3 Client (AWS SDK)              │
│ • Get temporary credentials         │
│   from IRSA (IAM Role for SA)       │
│ • STS AssumeRoleWithWebIdentity     │
│ • Credentials valid 15 minutes      │
└──────┬──────────────────────────────┘
       │ [3] HTTPS Request (TLS 1.2)
       │     POST https://secretsmanager.us-east-1.amazonaws.com/
       │     Headers:
       │       Authorization: AWS4-HMAC-SHA256 ...
       │       X-Amz-Security-Token: FwoGZXIv...
       │     Body:
       │       {
       │         "SecretId": "purple-parser/prod/anthropic-api-key"
       │       }
       ▼
┌─────────────────────────────────────┐
│ AWS Secrets Manager                 │
│ • Validate IAM credentials          │
│ • Check IAM policy permissions      │
│   └─ secretsmanager:GetSecretValue  │
│ • Retrieve encrypted secret blob    │
└──────┬──────────────────────────────┘
       │ [4] Encrypted Secret Blob
       │     KMS-encrypted AES-256-GCM
       ▼
┌─────────────────────────────────────┐
│ AWS KMS (Key Management Service)    │
│ • Validate decrypt permission       │
│   └─ kms:Decrypt on key ARN         │
│ • Decrypt secret using CMK          │
│ • Return plaintext secret           │
└──────┬──────────────────────────────┘
       │ [5] Decrypted Secret JSON
       │     {
       │       "api_key": "sk-ant-api03-...",
       │       "created_at": "2025-10-01T00:00:00Z",
       │       "version": "v1"
       │     }
       ▼
┌─────────────────────────────────────┐
│ boto3 Client                        │
│ • Parse JSON response               │
│ • Return to application             │
└──────┬──────────────────────────────┘
       │ [6] Secret Value
       ▼
┌─────────────────────────────────────┐
│ AWSSecretsManager Class              │
│ • Store in local cache              │
│   └─ cache[secret_name] = (value, time.time())                 │
│ • Set TTL = 300 seconds (5 min)     │
│ • Return value to caller            │
└──────┬──────────────────────────────┘
       │ [7] API Key String
       ▼
┌─────────────────────────────────────┐
│ Application Code                    │
│ api_key = "sk-ant-api03-..."        │
│ # Never logged or stored on disk    │
│ # Used for Anthropic API call       │
└─────────────────────────────────────┘


Parallel Flows:
────────────────
[Audit Logging]
  AWS Secrets Manager ──▶ CloudTrail
    • GetSecretValue API call logged
    • IAM principal (pod service account)
    • Timestamp
    • Source IP (VPC endpoint)
    • Result (success/denied)

[Metrics]
  boto3 Client ──▶ CloudWatch Metrics
    • Secret retrieval latency
    • Cache hit rate
    • Failure count

[Rotation]
  AWS Secrets Manager ──▶ Lambda (every 90 days)
    • Generate new API key
    • Update secret value
    • Trigger cache invalidation
    • Test new key
    • Deprecate old key (30-day grace)


Security Controls:
───────────────────
✅ Encryption in transit: TLS 1.2+ (HTTPS)
✅ Encryption at rest: AES-256-GCM (KMS)
✅ Authentication: IAM Role (IRSA)
✅ Authorization: IAM Policy (least privilege)
✅ Audit logging: CloudTrail (all API calls)
✅ Caching: 5-minute TTL (reduce API calls)
✅ No secrets in logs: Redacted from all logs
✅ No secrets on disk: Memory only
✅ Rotation: Automated (90-day cycle)

Performance:
─────────────
• First retrieval: 50-100ms (AWS API call)
• Cached retrieval: <1ms (memory lookup)
• Cache invalidation: Manual or automatic (rotation)
• Concurrent requests: Thread-safe cache

Failure Modes:
───────────────
• Secret not found → ValueError exception
• Permission denied → PermissionError exception
• Network timeout → Retry 3x with exponential backoff
• KMS decrypt failure → RuntimeError exception
• All failures logged to CloudWatch with CRITICAL level
```

---

## 5. Trust Boundary Analysis

### 5.1 Trust Boundary Crossing Points

```
┌─────────────────────────────────────────────────────────────────┐
│                  TRUST BOUNDARY CROSSING POINTS                  │
└─────────────────────────────────────────────────────────────────┘

Trust Level Legend:
───────────────────
🔴 ZERO TRUST (Internet)
🟠 LOW TRUST (DMZ)
🟡 MEDIUM TRUST (Application)
🟢 HIGH TRUST (AWS Services)

┌───────────────────────────────────────────────────────────────┐
│ 🔴 Trust Level 0: INTERNET (Zero Trust)                       │
│ • Public internet users                                       │
│ • Potential attackers                                         │
│ • No authentication required for initial connection           │
└────────┬──────────────────────────────────────────────────────┘
         │
         │ ⚠️  TRUST BOUNDARY 1: Internet → DMZ
         │ Controls:
         │   • TLS 1.2/1.3 mandatory
         │   • X.509 certificate validation
         │   • WAF (OWASP Top 10 rules)
         │   • DDoS protection (AWS Shield)
         │   • Rate limiting (1000 req/5min per IP)
         │   • Geographic restrictions (optional)
         │   • Bot detection (optional)
         │
         ▼
┌───────────────────────────────────────────────────────────────┐
│ 🟠 Trust Level 1: DMZ (Low Trust)                             │
│ • ALB with TLS termination                                    │
│ • NGINX Ingress Controller                                    │
│ • Public-facing components                                    │
│ • No sensitive data stored                                    │
└────────┬──────────────────────────────────────────────────────┘
         │
         │ ⚠️  TRUST BOUNDARY 2: DMZ → Application
         │ Controls:
         │   • Kubernetes Network Policies
         │   • Namespace isolation
         │   • Service mesh mTLS (optional)
         │   • Ingress controller authentication
         │   • Request validation
         │   • CSRF token validation
         │
         ▼
┌───────────────────────────────────────────────────────────────┐
│ 🟡 Trust Level 2: APPLICATION (Medium Trust)                  │
│ • Purple Parser containers                                    │
│ • Authenticated requests only                                 │
│ • Seccomp + AppArmor enforced                                 │
│ • Non-root execution                                          │
│ • Read-only root filesystem                                   │
└────────┬──────────────────────────────────────────────────────┘
         │
         │ ⚠️  TRUST BOUNDARY 3: Application → AWS Services
         │ Controls:
         │   • IAM Role (IRSA)
         │   • VPC Endpoints (no internet routing)
         │   • KMS encryption mandatory
         │   • Least privilege IAM policies
         │   • CloudTrail audit logging
         │   • Resource-based policies
         │
         ▼
┌───────────────────────────────────────────────────────────────┐
│ 🟢 Trust Level 3: AWS SERVICES (High Trust)                   │
│ • AWS Secrets Manager (CONFIDENTIAL data)                     │
│ • AWS KMS (encryption keys)                                   │
│ • CloudWatch Logs (audit trail)                               │
│ • S3 (long-term archive)                                      │
│ • Managed by AWS, high security baseline                      │
└───────────────────────────────────────────────────────────────┘
         │
         │ ⚠️  TRUST BOUNDARY 4: Application → External APIs
         │ Controls:
         │   • TLS 1.2/1.3 mandatory
         │   • API key authentication (from Secrets Manager)
         │   • Rate limiting (SDK-level)
         │   • Timeout enforcement (10s)
         │   • Response validation
         │   • Request logging (redact secrets)
         │
         ▼
┌───────────────────────────────────────────────────────────────┐
│ 🟡 Trust Level 2: EXTERNAL APIs (Medium Trust)                │
│ • Anthropic Claude API (verified partner)                     │
│ • SentinelOne API (verified partner)                          │
│ • Observo.ai API (verified partner)                           │
│ • GitHub API (public, rate-limited)                           │
└───────────────────────────────────────────────────────────────┘


Cross-Boundary Data Classification:
────────────────────────────────────
Boundary 1 (Internet → DMZ):
  • User input: INTERNAL (sanitized immediately)
  • Session cookies: CONFIDENTIAL (HTTPOnly, Secure, SameSite)

Boundary 2 (DMZ → Application):
  • Validated requests: INTERNAL
  • CSRF tokens: CONFIDENTIAL (HMAC-SHA256)

Boundary 3 (Application → AWS):
  • API keys: CONFIDENTIAL (encrypted at rest + in transit)
  • Application logs: INTERNAL (encrypted at rest + in transit)
  • Security events: CONFIDENTIAL (encrypted at rest + in transit)

Boundary 4 (Application → External):
  • API requests: INTERNAL (user data + prompts)
  • API responses: INTERNAL (generated code)
  • API keys in headers: CONFIDENTIAL (TLS-protected)


Security Incident Scenarios by Boundary:
──────────────────────────────────────────
Boundary 1 Breach (Internet → DMZ):
  • Attack: DDoS, WAF bypass, TLS downgrade
  • Impact: Service availability
  • Mitigation: AWS Shield, WAF rules, TLS enforcement
  • Detection: CloudWatch alarms on request rate

Boundary 2 Breach (DMZ → Application):
  • Attack: CSRF, XSS, authentication bypass
  • Impact: Unauthorized access to application
  • Mitigation: CSRF tokens, input validation, network policies
  • Detection: Failed CSRF validations, abnormal request patterns

Boundary 3 Breach (Application → AWS):
  • Attack: IAM credential theft, privilege escalation
  • Impact: Secrets exposure, log tampering
  • Mitigation: IRSA (short-lived creds), least privilege
  • Detection: CloudTrail anomalies, unauthorized API calls

Boundary 4 Breach (Application → External):
  • Attack: API key theft, man-in-the-middle
  • Impact: Unauthorized API usage, data interception
  • Mitigation: Secrets Manager, TLS 1.2+, certificate pinning
  • Detection: Abnormal API usage patterns, failed requests
```

---

## 6. Data Classification Flow

### 6.1 Data Lifecycle by Classification

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA CLASSIFICATION FLOW                      │
│                 Data Lifecycle from Input to Storage             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  CONFIDENTIAL Data (Highest Protection)                          │
│  • API Keys (Anthropic, SentinelOne, Observo.ai)                │
│  • CSRF Tokens                                                   │
│  • Session Cookies                                               │
└─────────────────────────────────────────────────────────────────┘

 Lifecycle:
 ──────────
 [Creation]
   • Generated by: AWS Secrets Manager (API keys) or application (tokens)
   • Encryption: AES-256-GCM (KMS)
   • Storage: AWS Secrets Manager or memory only

 [Transit]
   • Protocol: TLS 1.2/1.3
   • Cipher: ECDHE-RSA-AES256-GCM-SHA384
   • Validation: Certificate pinning (optional)

 [Usage]
   • Access: IAM role (IRSA) for API keys
   • Scope: Single request (tokens)
   • Caching: 5 minutes (API keys), none (tokens)

 [Logging]
   • API keys: NEVER logged (redacted)
   • Tokens: Logged as hash only (SHA-256)
   • Access: CloudTrail (AWS) or security logs

 [Destruction]
   • API keys: Rotation (90 days), old key deprecated (30-day grace)
   • Tokens: Cleared from memory after use
   • Cookies: Cleared on session end or logout


┌─────────────────────────────────────────────────────────────────┐
│  INTERNAL Data (Standard Protection)                             │
│  • User input (parser descriptions)                              │
│  • Generated Lua pipelines                                       │
│  • Application logs                                              │
│  • Configuration files                                           │
└─────────────────────────────────────────────────────────────────┘

 Lifecycle:
 ──────────
 [Creation]
   • User input: Web form or API
   • Lua pipelines: Generated by Claude API
   • Logs: Application runtime

 [Transit]
   • User input: TLS 1.2/1.3 (HTTPS)
   • Lua pipelines: Internal only (no transit)
   • Logs: TLS 1.2 to CloudWatch

 [Storage]
   • User input: Memory only (not persisted)
   • Lua pipelines: EBS volumes (AES-256 encrypted)
   • Logs: CloudWatch Logs (AES-256 KMS encrypted)

 [Processing]
   • Validation: All input sanitized and validated
   • Transformation: Lua code extracted and validated
   • Aggregation: Logs aggregated by Fluentd

 [Retention]
   • User input: Session only (cleared after response)
   • Lua pipelines: 30 days (automated cleanup)
   • Logs: 90 days (CloudWatch), 7 years (S3 Glacier)

 [Destruction]
   • User input: Garbage collected (Python)
   • Lua pipelines: Automated deletion script
   • Logs: CloudWatch retention policy


┌─────────────────────────────────────────────────────────────────┐
│  PUBLIC Data (Minimal Protection)                                │
│  • GitHub documentation (RAG sources)                            │
│  • Observo.ai public API documentation                           │
│  • Example parsers (from public repos)                           │
└─────────────────────────────────────────────────────────────────┘

 Lifecycle:
 ──────────
 [Acquisition]
   • Source: GitHub API (public repos)
   • Frequency: Daily (automated)
   • Validation: SHA-256 hash verification

 [Transit]
   • Protocol: HTTPS (TLS 1.2+)
   • Authentication: GitHub API key (rate limit only)

 [Storage]
   • Location: ChromaDB (vector database)
   • Encryption: Not required (public data)
   • Backup: S3 (standard encryption)

 [Usage]
   • Purpose: RAG context for Claude API
   • Access: All application components
   • Caching: Indefinite (until update)

 [Updates]
   • Frequency: Daily check for updates
   • Process: Re-ingest if SHA-256 changed
   • Rollback: Previous version kept for 7 days


Cross-Classification Data Flows:
──────────────────────────────────
Flow 1: User Input (INTERNAL) + API Key (CONFIDENTIAL) → Anthropic
  • User input sanitized, validated, never logged with API key
  • API key retrieved from Secrets Manager, used in Authorization header
  • Combined in memory only, transmitted over TLS 1.2+
  • Response (Lua code) treated as INTERNAL

Flow 2: Lua Code (INTERNAL) → EBS Storage → Observo.ai (INTERNAL)
  • Lua code validated, written to encrypted EBS
  • Optionally deployed to Observo.ai via API (TLS 1.2+)
  • Deployment status logged (no code in logs)

Flow 3: Logs (INTERNAL) → CloudWatch (INTERNAL) → S3 Glacier (INTERNAL)
  • Logs collected by Fluentd, transmitted over TLS 1.2
  • Stored in CloudWatch with KMS encryption (90 days)
  • Archived to S3 Glacier with KMS encryption (7 years)
  • All CONFIDENTIAL data redacted before logging


Data Classification Matrix:
────────────────────────────
| Data Type | Classification | Encryption at Rest | Encryption in Transit | Retention | Logging |
|-----------|----------------|--------------------|-----------------------|-----------|---------|
| API Keys | CONFIDENTIAL | AES-256 (KMS) | TLS 1.2+ | Until rotated | Never |
| CSRF Tokens | CONFIDENTIAL | Memory only | TLS 1.2+ | Single request | Hash only |
| Session Cookies | CONFIDENTIAL | Not stored | TLS 1.2+ | Session | Cookie ID only |
| User Input | INTERNAL | Not stored | TLS 1.2+ | Session only | Sanitized version |
| Lua Pipelines | INTERNAL | AES-256 (EBS) | TLS 1.2+ | 30 days | File path only |
| Application Logs | INTERNAL | AES-256 (KMS) | TLS 1.2+ | 90 days + 7y archive | Full logging |
| Config Files | INTERNAL | AES-256 (EBS) | TLS 1.2+ | Indefinite | Changes only |
| Public Docs | PUBLIC | Standard (S3) | TLS 1.2+ | Indefinite | Access patterns |
```

---

## Appendix A: DFD Notation Reference

### A.1 Symbols Used

| Symbol | Meaning | Example |
|--------|---------|---------|
| `┌─────┐` | External Entity | User, External API |
| `[1.0]` | Process | Main Parser Generator |
| `│ Data │` | Data Flow | API Key, User Input |
| `🔴 🟠 🟡 🟢` | Trust Level | Zero, Low, Medium, High |
| `⚠️` | Trust Boundary | Internet → DMZ |
| `├─┤` | Data Store | EBS, Secrets Manager |

### A.2 Data Flow Notation

- `─────▶`: Data flow direction
- `[A]`: Data flow label
- `HTTPS (TLS 1.2+)`: Protocol specification
- `(encrypted)`: Encryption status

---

## Appendix B: Threat Indicators

### B.1 Monitoring Points

Each trust boundary crossing has monitoring:

- Boundary 1: WAF logs, ALB access logs
- Boundary 2: NGINX access logs, network policy drops
- Boundary 3: CloudTrail (AWS API calls)
- Boundary 4: Application logs (external API calls)

### B.2 Alert Triggers

- Authentication failures > 5/5min
- CSRF validation failures > 10/hour
- Validation failures > 20/hour
- API errors > 50/hour
- Unexpected IAM calls (CloudTrail)

---

**Document Approval**

| Role | Name | Date |
|------|------|------|
| **Security Architect** | [Name] | 2025-10-10 |
| **ISSO** | [Name] | 2025-10-10 |

---

**End of Data Flow Diagrams Document**
