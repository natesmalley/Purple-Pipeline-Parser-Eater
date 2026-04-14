"""Phase 5.D - secret-leak guard regression test.

Runs scripts/check_secret_leaks.sh against the current repo and asserts it
exits 0. The script is the real gate; this test makes sure it actually runs
in CI and catches regressions.
"""
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_secret_leaks.sh"


@pytest.mark.skipif(
    not SCRIPT.exists(),
    reason="scripts/check_secret_leaks.sh not present",
)
def test_current_repo_passes_secret_scan():
    """The current repo HEAD must pass the secret-leak scan."""
    bash = os.environ.get("BASH_PATH", "bash")
    result = subprocess.run(
        [bash, str(SCRIPT), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"secret-leak scan failed:\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


@pytest.mark.skipif(
    not SCRIPT.exists(),
    reason="scripts/check_secret_leaks.sh not present",
)
def test_known_leaked_token_in_new_file_triggers_scan(tmp_path):
    """Drop the known-leaked token into a new file in a temp dir, run the scan,
    assert it fails with a LEAK message naming that file."""
    bad = tmp_path / "config.yaml"
    bad.write_text('default_token: "0_T5MMxAtfrW52/B1PyKw7_9LBinm515UzXuKy/wVUvY-"\n')

    bash = os.environ.get("BASH_PATH", "bash")
    result = subprocess.run(
        [bash, str(SCRIPT), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "expected secret-leak scan to fail on planted token"
    assert "LEAK" in result.stdout, f"expected LEAK in stdout: {result.stdout}"


@pytest.mark.skipif(
    not SCRIPT.exists(),
    reason="scripts/check_secret_leaks.sh not present",
)
def test_hec_shape_token_in_new_file_triggers_scan(tmp_path):
    """Drop a HEC-shaped token (not the specific leaked one) and verify the
    shape scan catches it."""
    bad = tmp_path / "config.yaml"
    bad.write_text('default_token: "abc123ABC456def789DEF0-_xyz9876543210_/+abcd"\n')

    bash = os.environ.get("BASH_PATH", "bash")
    result = subprocess.run(
        [bash, str(SCRIPT), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "LEAK" in result.stdout


@pytest.mark.skipif(
    not SCRIPT.exists(),
    reason="scripts/check_secret_leaks.sh not present",
)
def test_placeholder_token_passes(tmp_path):
    """Placeholder values like 'your-token-here' or 'PLACEHOLDER' must NOT trigger."""
    ok = tmp_path / "config.yaml.example"
    ok.write_text('default_token: "your-token-here"\n')

    bash = os.environ.get("BASH_PATH", "bash")
    result = subprocess.run(
        [bash, str(SCRIPT), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"placeholder scan failed: {result.stdout}"
