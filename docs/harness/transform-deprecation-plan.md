# transform(record) Controlled Deprecation Plan (PR-7)

## Purpose
Define an explicit, gated migration path from legacy `transform(record)` to canonical `processEvent(event)` without silent breakage.

## Policy
- Canonical contract remains `processEvent(event)`.
- `transform(record)` remains compatibility-only by default.
- No implicit removal is allowed.

## Gate Behavior
- Default behavior (backward-compatible):
  - Legacy `transform(record)` is accepted with a warning.
- Explicit gate behavior (opt-in):
  - Legacy-only `transform(record)` is rejected.
  - `processEvent(event)` remains accepted.
  - Mixed scripts containing both signatures remain allowed during migration and emit fallback warnings.

## Migration Requirements
- Parser owners should migrate legacy scripts to `processEvent(event)`.
- During migration windows, fallback definitions may remain temporarily for rollback safety.
- Before any future compatibility removal milestone:
  - regression matrix tests must pass,
  - migration guidance must be complete,
  - fallback behavior must be explicitly documented.
