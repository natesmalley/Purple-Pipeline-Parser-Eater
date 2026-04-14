.PHONY: test-fast

# Harness-first targeted test subset. Creates a throwaway venv at .venv-test
# so it will not clobber a developer's main .venv. Activation line works on
# both Windows bash (Scripts/activate) and Unix (bin/activate) — the first
# form fails silently on Unix and vice versa.
test-fast:
	python -m venv .venv-test || true
	. .venv-test/Scripts/activate 2>/dev/null || . .venv-test/bin/activate; \
	pip install --quiet -r requirements-test.txt; \
	pytest tests/test_harness_cli_smoke.py tests/test_harness_ocsf_alignment.py tests/test_workbench_jobs_api.py tests/test_parser_workbench.py -q
