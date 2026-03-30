# Harness Model and Scoring Strategy

## Purpose
Define the operational strategy for:
- Cheap-first, two-tier LLM generation
- Harness confidence scoring modules
- Observo Lua contract checks used for acceptance/rejection

This document is the reference for how a generated Lua script is judged before PR/deployment decisions.

## Two-Tier Model Strategy

### Goal
Control cost while preserving quality:
1. Generate with lower-cost model first.
2. Automatically escalate to a stronger model only when score remains below threshold.

### Tier Selection
- Provider is selected from available keys and `LLM_PROVIDER_PREFERENCE`.
- Primary model:
  - `OPENAI_MODEL` or `ANTHROPIC_MODEL`
- Strong fallback model:
  - `OPENAI_STRONG_MODEL` or `ANTHROPIC_STRONG_MODEL`
  - Defaults when unset:
    - OpenAI mini-class -> `gpt-5.2`
    - Anthropic haiku-class -> `claude-sonnet-4-5`

### Escalation Trigger
- If best score from primary model tier is `< score_threshold`, generator runs another tier with stronger model.
- Iteration history is carried into refinement prompts to avoid reintroducing prior defects.

### Implementation
- `components/agentic_lua_generator.py`
  - `AgenticLuaGenerator.generate(...)`
  - `_get_model_candidates(...)`
  - `_call_llm(..., model_override=...)`

## Confidence Scoring Modules

### Weighted Modules (0-100 final score)
- Lua validity: 25%
- Lua linting: 15%
- OCSF mapping: 25%
- Source field comparison: 15%
- Test execution: 20%

### Grade Mapping
- `A >= 90`
- `B >= 80`
- `C >= 70`
- `D >= 60`
- `F < 60`

### Implementation
- `components/testing_harness/harness_orchestrator.py`
  - `_compute_confidence(...)`

## Observo Lua Contract Checks

Reference:
- Observo Lua Script docs:
  - `processEvent(event)` is required entrypoint
  - return event (or `nil` to drop)
  - helper functions are allowed

URL:
- https://docs.observo.ai/6S3TPBguCvVUaX3Cy74P/working-with-data/transforms/functions/lua-script

### Lint Rules Enforcing Observo-Specific Expectations
- `observo_contract`:
  - Enforces `processEvent(event)` signature parameter naming.
- `return_or_emit`:
  - Ensures `processEvent` includes `return`.
- `helper_dependencies`:
  - Flags helper calls used in `processEvent` when helper is undefined.
  - Flags `local function` helpers declared after `processEvent` (Lua lexical scope risk).
- `ocsf_required_fields`:
  - Requires core OCSF output assignments (`class_uid`, `category_uid`, `time`, `activity_id`, `type_uid`, `severity_id`).

### Runtime Validation
- `test_execution` executes Lua against test events and records pass/fail and errors.
- Runtime failures (for example missing helper function at execution time) directly reduce score.

### Implementation
- `components/testing_harness/lua_linter.py`
- `components/testing_harness/dual_execution_engine.py`

## Decision Policy

### Accepted Candidate
- Score `>= threshold` (default threshold from generator/workbench context)
- No blocking runtime failures in harness execution path

### Needs Review
- Score below threshold or runtime/lint defects present
- Typical remediations:
  - Fill missing required OCSF fields (`activity_id` is a common miss)
  - Define helpers in script or place local helpers above `processEvent`
  - Correct return behavior and mapping consistency

## Test Coverage

Relevant tests:
- `tests/test_agentic_model_escalation.py`
- `tests/test_harness_lua_linter.py`
- `tests/test_parser_workbench.py`
- `tests/test_harness_ocsf_alignment.py`
- `tests/test_workbench_jobs_api.py`

Run smallest-first:
```bash
pytest tests/test_agentic_model_escalation.py -q
pytest tests/test_harness_lua_linter.py -q
```
