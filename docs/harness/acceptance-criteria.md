# Harness Acceptance Criteria

## Global Gates (Apply to Every Milestone)
- Scope is limited to the active milestone.
- Backward compatibility is preserved unless the milestone explicitly allows a change.
- Canonical Lua authoring contract remains `processEvent(event)`.
- `transform(record)` remains compatibility-only unless explicitly retired.
- Dataset iteration and report output ordering are deterministic.
- Existing `output/` corpus is not modified in place unless explicitly required by the milestone.
- Behavior changes include matching test additions/updates.
- Verification starts with the smallest relevant checks.

## Milestone-Specific Gates

### PR-0: Codex operating scaffolding
- `AGENTS.md` exists with repo-specific build/test/review guidance.
- `.codex/config.toml` exists with safe repo-local defaults.
- `docs/harness/technical-roadmap.md` exists and sequences milestones.
- `docs/harness/acceptance-criteria.md` exists and defines milestone gates.
- No runtime behavior changes.

### PR-1: Dataset model and fixture boundaries
- Dataset-first fixture model is documented and enforced in tests.
- Dataset ordering behavior is deterministic.
- No unrelated runtime refactors.

### PR-2: Lua contract normalization
- `processEvent(event)` path is first-class in harness flow.
- `transform(record)` compatibility path still passes regression tests.
- Contract behavior is covered by targeted tests.

### PR-3: Harness execution isolation
- Harness execution path is isolated from unrelated platform concerns.
- Compatibility adapters remain covered.
- Targeted harness tests pass.

### PR-4: Deterministic reporting
- Reports are stable across repeated runs with same dataset.
- Ordering rules are explicit and tested.

### PR-5: Compatibility regression expansion
- Compatibility matrix/regression set exists and passes.
- Legacy behavior expectations are documented in tests.

### PR-6: Standalone workflow hardening
- Primary standalone harness workflow is validated by smoke tests.
- Output determinism remains intact.

### PR-7: Controlled deprecation (if approved)
- Deprecation policy is explicit, tested, and documented.
- Migration path is validated before compatibility removal.

### PR-8: Stabilization and release
- Acceptance suite passes.
- Reproducibility checks pass on repeated runs.
- Documentation and milestone gates are complete.

## PR Verification Checklist Template
- Confirm changed files are only those intended for the milestone.
- Run smallest relevant checks first.
- Record exactly what was verified.
- Document risks/follow-ups without expanding milestone scope.
