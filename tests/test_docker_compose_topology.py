"""Stream A7 — docker-compose.yml two-service topology."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture(scope="module")
def compose():
    path = Path(__file__).resolve().parent.parent / "docker-compose.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_parser_eater_service_exists(compose):
    assert "parser-eater" in compose["services"]


def test_parser_eater_worker_service_exists(compose):
    assert "parser-eater-worker" in compose["services"]


def test_parser_eater_has_no_command_override(compose):
    svc = compose["services"]["parser-eater"]
    # Either no command key, or command does not run continuous_conversion_service.py
    cmd = svc.get("command")
    if cmd:
        flat = cmd if isinstance(cmd, str) else " ".join(cmd)
        assert "continuous_conversion_service.py" not in flat


def test_parser_eater_worker_uses_worker_only_flag(compose):
    svc = compose["services"]["parser-eater-worker"]
    cmd = svc["command"]
    flat = cmd if isinstance(cmd, str) else " ".join(cmd)
    assert "--worker-only" in flat
    assert "continuous_conversion_service.py" in flat


def test_both_services_mount_app_data(compose):
    for name in ("parser-eater", "parser-eater-worker"):
        svc = compose["services"][name]
        volumes = svc.get("volumes", [])
        names = []
        for v in volumes:
            if isinstance(v, dict):
                if v.get("source"):
                    names.append(v["source"])
            elif isinstance(v, str):
                names.append(v.split(":")[0])
        assert "app-data" in names, f"{name} does not mount app-data"


def test_worker_depends_on_parser_eater(compose):
    svc = compose["services"]["parser-eater-worker"]
    deps = svc.get("depends_on") or {}
    assert "parser-eater" in deps
    if isinstance(deps, dict):
        assert deps["parser-eater"].get("condition") == "service_healthy"


def test_parser_eater_has_upstream_tls_env(compose):
    svc = compose["services"]["parser-eater"]
    env = svc.get("environment", [])
    flat = " ".join(env) if isinstance(env, list) else " ".join(f"{k}={v}" for k, v in env.items())
    assert "WEB_UI_TLS_TERMINATED_UPSTREAM" in flat


def test_parser_eater_has_state_store_path(compose):
    svc = compose["services"]["parser-eater"]
    env = svc.get("environment", [])
    flat = " ".join(env) if isinstance(env, list) else " ".join(f"{k}={v}" for k, v in env.items())
    assert "STATE_STORE_PATH" in flat
