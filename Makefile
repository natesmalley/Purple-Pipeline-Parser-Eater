.PHONY: test-fast test-all

# Harness-first targeted test subset. Creates a throwaway venv at .venv-test
# so it will not clobber a developer's main .venv. Activation line works on
# both Windows bash (Scripts/activate) and Unix (bin/activate) — the first
# form fails silently on Unix and vice versa.
test-fast:
	python -m venv .venv-test || true
	. .venv-test/Scripts/activate 2>/dev/null || . .venv-test/bin/activate; \
	pip install --quiet -r requirements-test.txt; \
	pytest tests/test_harness_cli_smoke.py tests/test_harness_ocsf_alignment.py tests/test_workbench_jobs_api.py tests/test_parser_workbench.py -q

# Broader sweep across the full tests/ tree. Plan Phase 6.A widened the
# CI target from the narrow workbench/harness glob to the whole tests/
# tree. `--continue-on-collection-errors` is tolerated until the Phase 6
# zombie-test-or-fix follow-ups (V4a) land.
test-all:
	python -m venv .venv-test || true
	. .venv-test/Scripts/activate 2>/dev/null || . .venv-test/bin/activate; \
	pip install --quiet -r requirements-test.txt; \
	pytest tests/ --continue-on-collection-errors -q
