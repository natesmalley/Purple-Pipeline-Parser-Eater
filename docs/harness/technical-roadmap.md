# Harness Technical Roadmap

## Summary
This roadmap sequences the refactor toward a standalone, dataset-first OCSF/Lua testing harness using small, reviewable milestone PRs. Each PR should remain narrowly scoped and preserve compatibility unless explicitly stated otherwise.

## Milestone Sequence

### PR-0: Codex operating scaffolding
- Add repo-local agent guidance and harness roadmap/acceptance docs.
- No runtime behavior changes.
- Verification: file existence + changed-path checks only.

### PR-1: Dataset model and fixture boundaries
- Define dataset-first harness inputs and stable fixture layout.
- Separate dataset metadata from execution concerns.
- Non-goal: runtime execution refactor.
- Verification: targeted tests for dataset loading and ordering.

### PR-2: Lua contract normalization
- Make `processEvent(event)` the canonical harness authoring contract.
- Keep `transform(record)` as compatibility-only path.
- Non-goal: removing compatibility path.
- Verification: contract tests for both canonical and compatibility paths.

### PR-3: Harness execution isolation
- Isolate harness execution flow from broader platform runtime concerns.
- Clarify adapter boundaries for compatibility calls.
- Non-goal: platform-wide architecture rewrite.
- Verification: harness-focused execution tests.

### PR-4: Deterministic dataset/reporting behavior
- Enforce deterministic ordering in dataset traversal and report output.
- Add stable sort/normalization rules where needed.
- Non-goal: changing report semantics.
- Verification: repeatability tests across repeated runs.

### PR-5: Compatibility and regression expansion
- Expand regression coverage for legacy parsers and mixed contract usage.
- Track backward-compat guarantees in tests.
- Non-goal: deprecation/removal actions.
- Verification: targeted compatibility matrix tests.

### PR-6: Standalone harness UX and workflow hardening
- Improve harness operator workflow (CLI/report ergonomics) without widening scope.
- Preserve deterministic outputs and fixture contract.
- Non-goal: platform runtime feature expansion.
- Verification: smoke tests for primary standalone workflows.

### PR-7: Controlled deprecation planning (optional milestone)
- If approved, document and gate a deprecation path for `transform(record)`.
- Include migration notes and fallback behavior requirements.
- Non-goal: silent or implicit compatibility removal.
- Verification: deprecation warnings/tests and migration validation.

### PR-8: Stabilization and release gate
- Final pass on harness docs, deterministic outputs, and regression reliability.
- Lock acceptance gates for handoff.
- Non-goal: introducing new capability scope.
- Verification: agreed acceptance suite + reproducibility checks.

## Execution Principles for All Milestones
- Implement only the active milestone.
- Keep diffs small and reviewable.
- Update tests for changed behavior.
- Prefer smallest relevant verification first.
- Avoid unrelated platform code changes.
