"""FU8 (R4) — agentic_lua_generator wrap-idempotence fallback regression tests.

W8 fixed the daemon-path silent unwrap fallback at
``components/lua_generator.py:466-467``. Two siblings remained in
``components/agentic_lua_generator.py``:

  (1) GPT-5 strategy boundary — wraps ``raw_lua`` at the deploy step inside
      ``_run_gpt5_strategy``.
  (2) Shim deploy boundary — wraps ``result.lua_code`` at the end of
      ``AgenticLuaGenerator.generate``.

Both previously caught a blanket ``ValueError`` and silently fell through
to the unwrapped body, which would let the daemon ship Lua the standalone
dataplane refuses to load (the W8 bug, ported into the agentic shim).

FU8 introduces ``_is_wrap_idempotence_error(exc)`` as the single source
of truth for distinguishing the two known idempotence raises (sentinel
match / secondary heuristic — see
``components/lua_deploy_wrapper.py:165 + 176``) from any OTHER
``ValueError``. Idempotence keeps the existing forgiving behavior. Other
errors get the W8 rejected-shape contract.

Test plan: 4 helper unit tests + 6 boundary regression tests (sentinel
+ secondary + synthetic, across both call sites) + 2 positive controls.
"""
from pathlib import Path

import pytest

from components.agentic_lua_generator import (
    AgenticLuaGenerator,
    _is_wrap_idempotence_error,
)


# ---------------------------------------------------------------------------
# Helper unit tests — _is_wrap_idempotence_error
# ---------------------------------------------------------------------------


def test_helper_true_on_sentinel_message():
    """The verbatim sentinel-marker raise from
    components/lua_deploy_wrapper.py:165 must be classified as idempotence.
    """
    exc = ValueError(
        "lua_body is already wrapped by wrap_for_observo "
        "(found sentinel marker '-- @observo:wrap-once'). "
        "Do not wrap twice."
    )
    assert _is_wrap_idempotence_error(exc) is True


def test_helper_true_on_secondary_heuristic_message():
    """The verbatim secondary-heuristic raise from
    components/lua_deploy_wrapper.py:176 must be classified as idempotence.
    """
    exc = ValueError(
        "lua_body appears to already define function process(event, emit). "
        "Do not wrap twice."
    )
    assert _is_wrap_idempotence_error(exc) is True


def test_helper_false_on_synthetic_message():
    """Any OTHER ValueError message must NOT be classified as idempotence.
    This guards against silent passthrough of future contract violations.
    """
    exc = ValueError("synthetic unexpected wrap failure: bad helper inline")
    assert _is_wrap_idempotence_error(exc) is False


def test_helper_false_on_empty_message():
    """An empty-message ValueError carries no idempotence marker and must
    fail the check — defensive against bare ``raise ValueError()``.
    """
    exc = ValueError()
    assert _is_wrap_idempotence_error(exc) is False


# ---------------------------------------------------------------------------
# Shared stubs for the GPT-5 + shim deploy boundary tests
# ---------------------------------------------------------------------------


class _HarnessStub:
    """Minimal harness stub — same shape as test_gpt5_strategy_flow."""

    def run_all_checks(
        self, lua_code, parser_config, ocsf_version="1.3.0", custom_test_events=None,
    ):
        return {
            "confidence_score": 84,
            "confidence_grade": "B",
            "checks": {
                "field_comparison": {"coverage_pct": 85},
                "lua_linting": {"issues": []},
                "ocsf_mapping": {
                    "missing_required": [],
                    "class_uid": 4003,
                    "class_name": "DNS Activity",
                },
            },
            "ocsf_alignment": {"required_coverage": 100.0},
        }


class _SourceStub:
    def analyze_parser(self, parser_entry):
        return {"fields": [{"name": "message", "type": "string"}]}


class _GPT5FlowGenerator(AgenticLuaGenerator):
    """GPT-5 short-circuit driver: stubs out the OpenAI Responses API so
    we control the flow into the wrap_for_observo call site.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

    def _call_openai_responses_raw(
        self,
        model,
        instructions,
        input_items,
        previous_response_id=None,
        response_format=None,
    ):
        self.calls.append(
            {
                "model": model,
                "response_format": response_format,
                "previous_response_id": previous_response_id,
            }
        )
        if response_format:
            # planner call
            return {
                "text": (
                    '{"class_uid":4003,"class_name":"DNS Activity",'
                    '"category_uid":4,"category_name":"Network Activity",'
                    '"activity_id":1,"activity_name":"DNS Query",'
                    '"timestamp_sources":["timestamp"],'
                    '"severity_strategy":"default 0",'
                    '"embedded_payload_strategy":"parse message kv",'
                    '"mappings":[{"target":"src_endpoint.ip",'
                    '"source_candidates":["cliIP"],"transform":"direct",'
                    '"required":false}],'
                    '"notes":["parse embedded payload"]}'
                ),
                "response_id": "resp_plan",
                "data": {},
            }
        return {
            "text": "function processEvent(event)\n  return event\nend",
            "response_id": "resp_code",
            "data": {},
        }


def _make_gpt5_generator(tmp_path: Path) -> _GPT5FlowGenerator:
    gen = _GPT5FlowGenerator(
        api_key="test-key",
        model="gpt-5-mini",
        provider="openai",
        max_iterations=1,
        score_threshold=80,
        output_dir=tmp_path,
    )
    gen.harness = _HarnessStub()
    gen.source_analyzer = _SourceStub()
    return gen


def _gpt5_parser_entry() -> dict:
    return {
        "parser_name": "akamai_dns-fu8",
        "ingestion_mode": "push",
        # raw_examples sets workbench_run=True so cache.put is skipped — the
        # wrap fallback path is the only thing under test here.
        "raw_examples": [{"message": 'AkamaiDNS cliIP="1.2.3.4"'}],
        "config": {
            "attributes": {
                "dataSource": {"vendor": "Akamai", "product": "DNS"},
            },
        },
    }


# ---------------------------------------------------------------------------
# GPT-5 boundary regression tests
# ---------------------------------------------------------------------------


def test_gpt5_boundary_sentinel_idempotence_keeps_unwrapped(monkeypatch, tmp_path):
    """Sentinel-message ValueError out of wrap_for_observo at the GPT-5
    boundary must preserve the existing forgiving behavior:
    ``final_lua == raw_lua`` and the result still flags accepted/below_threshold
    based on score (NOT 'rejected').
    """
    raw_lua = "function processEvent(event)\n  return event\nend"

    def _raise_sentinel(_lua_body: str) -> str:
        raise ValueError(
            "lua_body is already wrapped by wrap_for_observo "
            "(found sentinel marker '-- @observo:wrap-once'). "
            "Do not wrap twice."
        )

    monkeypatch.setattr(
        "components.agentic_lua_generator.wrap_for_observo",
        _raise_sentinel,
    )

    gen = _make_gpt5_generator(tmp_path)
    result = gen.generate(_gpt5_parser_entry(), force_regenerate=True)

    # Score 84 >= threshold 80 -> "accepted"; the wrap fallback used raw_lua.
    assert result["quality"] == "accepted", (
        f"sentinel idempotence must NOT flip quality to rejected; got "
        f"{result['quality']!r}"
    )
    assert result["lua_code"] == raw_lua
    assert result["confidence_score"] == 84
    # Success contract is preserved on idempotence.
    assert getattr(result, "success", True) is True
    assert getattr(result, "error", None) is None


def test_gpt5_boundary_secondary_heuristic_idempotence_keeps_unwrapped(
    monkeypatch, tmp_path,
):
    """Secondary-heuristic ValueError out of wrap_for_observo at the GPT-5
    boundary must also be treated as idempotence and preserve the
    existing behavior.
    """
    raw_lua = "function processEvent(event)\n  return event\nend"

    def _raise_secondary(_lua_body: str) -> str:
        raise ValueError(
            "lua_body appears to already define function process(event, emit). "
            "Do not wrap twice."
        )

    monkeypatch.setattr(
        "components.agentic_lua_generator.wrap_for_observo",
        _raise_secondary,
    )

    gen = _make_gpt5_generator(tmp_path)
    result = gen.generate(_gpt5_parser_entry(), force_regenerate=True)

    assert result["quality"] == "accepted"
    assert result["lua_code"] == raw_lua
    assert result["confidence_score"] == 84
    assert getattr(result, "success", True) is True
    assert getattr(result, "error", None) is None


def test_gpt5_boundary_synthetic_valueerror_rejects(monkeypatch, tmp_path):
    """Any non-idempotence ValueError out of wrap_for_observo at the GPT-5
    boundary must reject with the W8 contract: quality='rejected',
    confidence_score=0.0, confidence_grade='F', success=False, populated
    error containing the underlying message.
    """
    def _raise_synthetic(_lua_body: str) -> str:
        raise ValueError("synthetic unexpected wrap failure")

    monkeypatch.setattr(
        "components.agentic_lua_generator.wrap_for_observo",
        _raise_synthetic,
    )

    gen = _make_gpt5_generator(tmp_path)
    result = gen.generate(_gpt5_parser_entry(), force_regenerate=True)

    assert result["quality"] == "rejected", (
        f"non-idempotence ValueError must reject; got {result['quality']!r}"
    )
    assert result["confidence_score"] == 0.0
    assert result["confidence_grade"] == "F"
    assert getattr(result, "success", True) is False
    error_msg = getattr(result, "error", None) or result.get("error", "")
    assert "synthetic" in (error_msg or ""), (
        f"underlying ValueError text must round-trip into result.error; "
        f"got {error_msg!r}"
    )


def test_gpt5_boundary_wrap_success_path_unchanged(monkeypatch, tmp_path):
    """Positive control: when wrap_for_observo succeeds at the GPT-5
    boundary, the result keeps the legacy accepted contract and lua_code
    is the wrapped body.
    """
    def _wrap_ok(lua_body: str) -> str:
        return f"-- wrapped\n{lua_body}\n-- end"

    monkeypatch.setattr(
        "components.agentic_lua_generator.wrap_for_observo",
        _wrap_ok,
    )

    gen = _make_gpt5_generator(tmp_path)
    result = gen.generate(_gpt5_parser_entry(), force_regenerate=True)

    assert result["quality"] == "accepted"
    assert result["confidence_score"] == 84
    assert result["lua_code"].startswith("-- wrapped")
    assert getattr(result, "success", True) is True
    assert getattr(result, "error", None) is None


# ---------------------------------------------------------------------------
# Shim deploy boundary regression tests (AgenticLuaGenerator.generate
# wrap-at-deploy step, after _run_iterative_loop_sync)
# ---------------------------------------------------------------------------


def _make_iterative_result_double() -> object:
    """Stand-in GenerationResult with the fields the shim deploy boundary
    reads/mutates. Avoids importing the real dataclass to keep the test
    surface minimal.
    """
    from components.lua_generator import GenerationResult

    return GenerationResult(
        parser_id="akamai_dns-fu8",
        parser_name="akamai_dns-fu8",
        lua_code="function processEvent(event)\n  return event\nend",
        confidence_score=82.0,
        confidence_grade="B",
        iterations=1,
        quality="accepted",
        model="claude-haiku-4-5-20251001",
        ingestion_mode="push",
        ocsf_class_name="DNS Activity",
        ocsf_class_uid=4003,
        generation_method="agentic_llm",
        elapsed_seconds=0.0,
        vendor="Akamai",
        product="DNS",
        success=True,
    )


def _make_shim_generator(tmp_path: Path, monkeypatch) -> AgenticLuaGenerator:
    """AgenticLuaGenerator with the inner iterative loop stubbed out so we
    drive straight to the wrap-at-deploy step.
    """
    gen = AgenticLuaGenerator(
        api_key="test-key",
        model="claude-haiku-4-5-20251001",
        provider="anthropic",
        max_iterations=1,
        score_threshold=70,
        output_dir=tmp_path,
    )
    gen.harness = _HarnessStub()
    gen.source_analyzer = _SourceStub()

    def _fake_iterative(*args, **kwargs):
        return _make_iterative_result_double()

    monkeypatch.setattr(
        gen._inner, "_run_iterative_loop_sync", _fake_iterative,
    )
    return gen


def _shim_parser_entry() -> dict:
    return {
        "parser_name": "akamai_dns-fu8",
        "ingestion_mode": "push",
        "raw_examples": [{"message": "test"}],
        "config": {
            "attributes": {
                "dataSource": {"vendor": "Akamai", "product": "DNS"},
            },
        },
    }


def test_shim_deploy_sentinel_idempotence_logs_and_keeps_unwrapped(
    monkeypatch, tmp_path, caplog,
):
    """Shim deploy boundary: sentinel-message ValueError must log a warning
    and preserve the unwrapped body — no quality flip.
    """
    raw_lua = "function processEvent(event)\n  return event\nend"

    def _raise_sentinel(_lua_body: str) -> str:
        raise ValueError(
            "lua_body is already wrapped by wrap_for_observo "
            "(found sentinel marker '-- @observo:wrap-once'). Do not wrap twice."
        )

    monkeypatch.setattr(
        "components.agentic_lua_generator.wrap_for_observo",
        _raise_sentinel,
    )

    gen = _make_shim_generator(tmp_path, monkeypatch)
    with caplog.at_level("WARNING", logger="components.agentic_lua_generator"):
        result = gen.generate(_shim_parser_entry(), force_regenerate=True)

    # Existing forgiving contract preserved: quality stays 'accepted',
    # body is the unwrapped raw_lua, no error set.
    assert result.quality == "accepted"
    assert result.lua_code == raw_lua
    assert result.success is True
    assert result.error is None
    # Warning text mentions the legacy "skipping double-wrap" phrasing.
    assert any(
        "skipping double-wrap" in record.message
        for record in caplog.records
    ), f"expected double-wrap warning, got {[r.message for r in caplog.records]!r}"


def test_shim_deploy_secondary_heuristic_idempotence_keeps_unwrapped(
    monkeypatch, tmp_path,
):
    """Shim deploy boundary: secondary-heuristic ValueError must also be
    treated as idempotence (warn + keep unwrapped body).
    """
    raw_lua = "function processEvent(event)\n  return event\nend"

    def _raise_secondary(_lua_body: str) -> str:
        raise ValueError(
            "lua_body appears to already define function process(event, emit). "
            "Do not wrap twice."
        )

    monkeypatch.setattr(
        "components.agentic_lua_generator.wrap_for_observo",
        _raise_secondary,
    )

    gen = _make_shim_generator(tmp_path, monkeypatch)
    result = gen.generate(_shim_parser_entry(), force_regenerate=True)

    assert result.quality == "accepted"
    assert result.lua_code == raw_lua
    assert result.success is True
    assert result.error is None


def test_shim_deploy_synthetic_valueerror_rejects(monkeypatch, tmp_path):
    """Shim deploy boundary: any non-idempotence ValueError must reject
    with the W8 contract — quality='rejected', confidence_score=0.0,
    confidence_grade='F', success=False, error populated with the
    underlying message.
    """
    def _raise_synthetic(_lua_body: str) -> str:
        raise ValueError("synthetic unexpected wrap failure")

    monkeypatch.setattr(
        "components.agentic_lua_generator.wrap_for_observo",
        _raise_synthetic,
    )

    gen = _make_shim_generator(tmp_path, monkeypatch)
    result = gen.generate(_shim_parser_entry(), force_regenerate=True)

    assert result.quality == "rejected", (
        f"non-idempotence ValueError must reject; got {result.quality!r}"
    )
    assert result.confidence_score == 0.0
    assert result.confidence_grade == "F"
    assert result.success is False
    assert result.error is not None
    assert "synthetic" in result.error


def test_shim_deploy_wrap_success_path_unchanged(monkeypatch, tmp_path):
    """Positive control: when wrap_for_observo succeeds at the shim deploy
    boundary, the wrapped body is returned and the quality/grade stay
    whatever the iteration loop produced.
    """
    def _wrap_ok(lua_body: str) -> str:
        return f"-- wrapped\n{lua_body}\n-- end"

    monkeypatch.setattr(
        "components.agentic_lua_generator.wrap_for_observo",
        _wrap_ok,
    )

    gen = _make_shim_generator(tmp_path, monkeypatch)
    result = gen.generate(_shim_parser_entry(), force_regenerate=True)

    assert result.lua_code.startswith("-- wrapped")
    assert result.quality == "accepted"
    assert result.success is True
    assert result.error is None
