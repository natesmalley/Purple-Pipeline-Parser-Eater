# AGENTS.md

## Purpose
This repository is being refactored incrementally into a standalone, dataset-first OCSF/Lua testing harness. Execute only the current milestone; do not pre-implement later milestones.

## Current Contract Rules
- Canonical Lua authoring contract is `processEvent(event)`.
- Legacy `transform(record)` is compatibility-only, not the new default.
- Preserve backward compatibility unless a milestone explicitly removes it.

## Scope and Safety Rules
- Do not expand scope beyond the active milestone.
- Do not refactor unrelated platform code while working on harness milestones.
- Keep dataset processing and report ordering deterministic.
- Do not modify the existing `output/` corpus in place unless the milestone explicitly requires it.

## Testing and Verification Rules
- In milestones that change behavior, always add or update tests for the changed behavior.
- Run the smallest relevant verification first, then widen only if needed.
- Prefer targeted pytest invocation before broader suites.

## Practical Repo Guidance
- Use `rg`/`rg --files` for fast discovery.
- Keep diffs small and reviewable; avoid unrelated formatting churn.
- If runtime behavior is intentionally unchanged, verify with path-scoped checks (`git diff --name-only`, targeted tests if applicable).
- This repo is harness-first; avoid reintroducing legacy ingestion/output stacks that were removed.

## Build/Test/Review Commands
- Environment: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Smallest verification first: `git diff --name-only` and targeted file existence checks.
- Targeted harness tests (later milestones): `pytest tests/test_workbench_jobs_api.py -q`, `pytest tests/test_parser_workbench.py -q`, `pytest tests/test_harness_ocsf_alignment.py -q`
- Broader validation only when needed: `pytest tests/test_workbench_*.py tests/test_parser_workbench.py tests/test_harness_*.py -v`
- Review before handoff: `git status --short` and `git diff -- AGENTS.md .codex/config.toml docs/harness/technical-roadmap.md docs/harness/acceptance-criteria.md`

## Review Checklist (Per Milestone PR)
- Changes are limited to the active milestone.
- Compatibility expectations are explicitly preserved or intentionally changed.
- Deterministic ordering constraints are maintained.
- Tests cover changed behavior (when behavior changed).
- Verification is minimal-but-sufficient and documented in the PR summary.
