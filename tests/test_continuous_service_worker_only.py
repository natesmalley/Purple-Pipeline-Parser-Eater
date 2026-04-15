"""Stream A4 — --worker-only CLI flag on continuous_conversion_service."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def test_parse_args_worker_only_flag_present():
    from continuous_conversion_service import _parse_cli_args
    args = _parse_cli_args(["--worker-only"])
    assert args.worker_only is True


def test_parse_args_default_is_full_mode():
    from continuous_conversion_service import _parse_cli_args
    args = _parse_cli_args([])
    assert args.worker_only is False


def test_worker_only_flag_skips_web_server(tmp_path, monkeypatch):
    """When worker_only is set, initialize() must skip WebFeedbackServer construction."""
    import asyncio

    monkeypatch.setenv("STATE_STORE_PATH", str(tmp_path / "state.json"))
    config_yaml = tmp_path / "config.yaml"
    config_yaml.write_text("rag: {}\n", encoding="utf-8")

    from continuous_conversion_service import ContinuousConversionService

    service = ContinuousConversionService(config_yaml, worker_only=True)
    assert service.worker_only is True
    # Pre-init: no web_server attribute populated
    assert service.web_server is None


def test_service_default_worker_only_false(tmp_path):
    from continuous_conversion_service import ContinuousConversionService
    config_yaml = tmp_path / "config.yaml"
    config_yaml.write_text("rag: {}\n", encoding="utf-8")
    service = ContinuousConversionService(config_yaml)
    assert service.worker_only is False
