"""FU17 - Cost ledger tests.

Mirrors components/feedback_channel.py's atomicity contract:
  - O_APPEND + single os.write per record
  - <= MAX_RECORD_BYTES (PIPE_BUF guarantee floor)
  - threading.Lock for own-process serialization
  - Cross-process atomicity via O_APPEND, NOT the lock

CRITICAL: cross-process safety is exercised via ``multiprocessing.Process``,
not just threads. The GIL serializes Python-level writes from threads in
the same process for free, so a threads-only test cannot prove cross-process
correctness.

The ``_live_module()`` pattern (used in FU13/14/15 tests) avoids
test-order pollution from earlier modules that may have monkeypatched
``components.cost_ledger`` symbols.
"""
from __future__ import annotations

import gzip
import importlib
import json
import multiprocessing as mp
import os
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _live_module():
    return importlib.import_module("components.cost_ledger")


# Note: the project-wide ``_isolate_cost_ledger_globally`` autouse
# fixture in ``tests/conftest.py`` already redirects COST_LEDGER_PATH
# to a per-test tmp_path and resets the singleton. We rely on that
# here — no local fixture needed. (Round-1 of FU17 had a local
# fixture; promoted to conftest in round-2 per DA-FU17 Fix 4.)


def _make_record(**overrides):
    base = {
        "parser_name": "cisco_duo",
        "provider": "anthropic",
        "model": "claude-opus-4-7",
        "iteration": 1,
        "tokens_in": 100,
        "tokens_out": 50,
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# Happy path                                                                  #
# --------------------------------------------------------------------------- #


class TestRecordHappyPath:
    def test_record_appends_jsonl_row(self, tmp_path):
        mod = _live_module()
        path = tmp_path / "ledger.jsonl"
        ledger = mod.CostLedger(path=path)
        ledger.record(**_make_record())
        assert path.exists()
        line = path.read_text(encoding="utf-8").strip()
        row = json.loads(line)
        assert row["parser_name"] == "cisco_duo"
        assert row["provider"] == "anthropic"
        assert row["model"] == "claude-opus-4-7"
        assert row["tokens_in"] == 100
        assert row["tokens_out"] == 50
        # ts present and looks ISO-8601-ish
        assert "ts" in row
        assert row["ts"].endswith("Z")

    def test_multiple_records_each_on_own_line(self, tmp_path):
        mod = _live_module()
        path = tmp_path / "ledger.jsonl"
        ledger = mod.CostLedger(path=path)
        for i in range(5):
            ledger.record(**_make_record(parser_name=f"row_{i}"))
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 5
        names = [json.loads(line)["parser_name"] for line in lines]
        assert names == [f"row_{i}" for i in range(5)]

    def test_record_with_optional_fields(self, tmp_path):
        mod = _live_module()
        path = tmp_path / "ledger.jsonl"
        ledger = mod.CostLedger(path=path)
        ledger.record(
            **_make_record(),
            cache_read=42,
            thinking_tokens=128,
            cache_breakpoints_used=2,
            response_id="resp_abc123",
            finish_reason="end_turn",
            latency_ms=1500,
        )
        row = json.loads(path.read_text(encoding="utf-8").strip())
        assert row["cache_read"] == 42
        assert row["thinking_tokens"] == 128
        assert row["cache_breakpoints_used"] == 2
        assert row["response_id"] == "resp_abc123"
        assert row["finish_reason"] == "end_turn"
        assert row["latency_ms"] == 1500

    def test_record_creates_parent_dir(self, tmp_path):
        mod = _live_module()
        path = tmp_path / "nested" / "deeper" / "ledger.jsonl"
        ledger = mod.CostLedger(path=path)
        ledger.record(**_make_record())
        assert path.exists()


# --------------------------------------------------------------------------- #
# Validation                                                                  #
# --------------------------------------------------------------------------- #


class TestRecordValidation:
    def test_record_oversize_rejects(self, tmp_path):
        mod = _live_module()
        ledger = mod.CostLedger(path=tmp_path / "ledger.jsonl")
        # Build a parser_name that exceeds the 2048 byte cap by itself
        huge = "x" * 5000
        with pytest.raises(ValueError, match="byte cap"):
            ledger.record(**_make_record(parser_name=huge))

    def test_encoded_newline_rejected(self, tmp_path):
        """If json serialization ever yields a literal newline, reject.

        json.dumps escapes \\n inside strings as \\\\n by default, so a
        plain newline in a value will NOT produce a literal newline in
        the encoded record. The validator exists as belt-and-suspenders.
        Force the path by patching json.dumps to return a string that
        contains a literal newline so we can exercise the check.
        """
        mod = _live_module()
        ledger = mod.CostLedger(path=tmp_path / "ledger.jsonl")
        import json as _json
        original_dumps = _json.dumps

        def _evil_dumps(*args, **kwargs):
            return original_dumps(*args, **kwargs) + "\n<polluted>"

        from unittest.mock import patch
        with patch("components.cost_ledger.json.dumps", side_effect=_evil_dumps):
            with pytest.raises(ValueError, match="newline"):
                ledger.record(**_make_record())

    def test_record_excludes_lua_body_and_pii(self, tmp_path):
        """Schema must NOT carry Lua bodies, prompt text, or sample data."""
        mod = _live_module()
        path = tmp_path / "ledger.jsonl"
        ledger = mod.CostLedger(path=path)
        ledger.record(**_make_record())
        row = json.loads(path.read_text(encoding="utf-8").strip())
        forbidden_keys = {
            "lua",
            "lua_body",
            "raw_examples",
            "system",
            "messages",
            "prompt",
            "response_text",
            "text",
            "samples",
        }
        intersection = forbidden_keys & set(row.keys())
        assert not intersection, f"unexpected key(s) in cost row: {intersection}"

    def test_file_permissions_640(self, tmp_path):
        if os.name == "nt":
            pytest.skip("file mode bits don't apply on Windows")
        mod = _live_module()
        path = tmp_path / "ledger.jsonl"
        ledger = mod.CostLedger(path=path)
        ledger.record(**_make_record())
        # World bits MUST NOT be set (the whole point of 0640 over 0644).
        assert (path.stat().st_mode & 0o007) == 0
        # Owner read+write must be set; group read must be set.
        assert (path.stat().st_mode & 0o600) == 0o600
        assert (path.stat().st_mode & 0o040) == 0o040


# --------------------------------------------------------------------------- #
# Singleton                                                                   #
# --------------------------------------------------------------------------- #


class TestSingleton:
    def test_get_default_ledger_returns_singleton(self, monkeypatch, tmp_path):
        mod = _live_module()
        monkeypatch.setenv("COST_LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
        mod.set_default_ledger(None)  # reset
        a = mod.get_default_ledger()
        b = mod.get_default_ledger()
        assert a is b

    def test_set_default_ledger_overrides(self, tmp_path):
        mod = _live_module()
        custom = mod.CostLedger(path=tmp_path / "custom.jsonl")
        mod.set_default_ledger(custom)
        assert mod.get_default_ledger() is custom
        # Cleanup so other tests don't see the override
        mod.set_default_ledger(None)

    def test_set_default_ledger_none_resets(self, monkeypatch, tmp_path):
        mod = _live_module()
        monkeypatch.setenv("COST_LEDGER_PATH", str(tmp_path / "reset.jsonl"))
        first = mod.CostLedger(path=tmp_path / "first.jsonl")
        mod.set_default_ledger(first)
        assert mod.get_default_ledger() is first
        mod.set_default_ledger(None)
        # Next call re-resolves env / defaults
        rebuilt = mod.get_default_ledger()
        assert rebuilt is not first


# --------------------------------------------------------------------------- #
# Concurrency                                                                 #
# --------------------------------------------------------------------------- #


class TestConcurrency:
    def test_concurrent_threads_no_overwrite(self, tmp_path):
        """200 records across 2 threads -> exactly 200 valid JSON lines."""
        mod = _live_module()
        ledger = mod.CostLedger(path=tmp_path / "ledger.jsonl")

        def worker(worker_id):
            for i in range(100):
                ledger.record(**_make_record(parser_name=f"w{worker_id}_r{i}"))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 200
        # Every line parses (no torn writes)
        names = set()
        for line in lines:
            row = json.loads(line)
            assert "parser_name" in row
            names.add(row["parser_name"])
        # All 200 unique names landed
        assert len(names) == 200


# --- multiprocessing worker (top-level so spawn-mode can re-import it) ---
def _process_worker(path_str: str, worker_id: int, count: int) -> None:
    """Top-level so multiprocessing.Process child interpreters can re-import."""
    import importlib as _il
    mod = _il.import_module("components.cost_ledger")
    ledger = mod.CostLedger(path=Path(path_str))
    for i in range(count):
        ledger.record(
            parser_name=f"p{worker_id}_r{i}",
            provider="anthropic",
            model="claude-opus-4-7",
            iteration=1,
            tokens_in=100,
            tokens_out=50,
        )


class TestCrossProcessConcurrency:
    """THIS is the test that proves cross-process safety.

    Threads alone don't prove the cross-process atomic-append claim
    because the GIL serializes Python-level writes for free. We need
    actual ``multiprocessing.Process`` instances with separate Python
    interpreters.

    Skipped on Windows — and not just for CI-speed reasons. Verified
    locally that 5 trials of 2-process x 100-record runs on Windows
    produce 198-200 lines instead of a deterministic 200, because the
    Windows CRT does NOT honor the POSIX ``O_APPEND`` atomic-write
    contract that this module's correctness rests on. The same
    workload on Linux (verified via WSL) produces exactly 200 lines
    every time. Production deployments target Linux containers
    (gunicorn + worker compose stack), so the POSIX guarantee is the
    one we actually depend on.
    """

    def test_concurrent_processes_no_overwrite(self, tmp_path):
        if os.name == "nt":
            pytest.skip(
                "Windows CRT does not honor POSIX O_APPEND atomicity; "
                "verified on Linux (WSL) that the same workload "
                "produces exactly 200 rows every trial. Production "
                "is Linux-only."
            )

        path = tmp_path / "ledger.jsonl"
        procs = [
            mp.Process(target=_process_worker, args=(str(path), wid, 100))
            for wid in range(2)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=30)
            assert p.exitcode == 0, f"worker {p.pid} exited with {p.exitcode}"

        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 200, (
            f"expected 200 rows, got {len(lines)} (cross-process race?)"
        )
        # Every line valid JSON, every record uniquely identifiable
        parser_names = set()
        for line in lines:
            row = json.loads(line)  # raises on torn write
            parser_names.add(row["parser_name"])
        assert len(parser_names) == 200, (
            "duplicate parser_name across rows - append-and-overwrite race"
        )


# --------------------------------------------------------------------------- #
# Rotation                                                                    #
# --------------------------------------------------------------------------- #


class TestRotation:
    def test_rotation_at_threshold_creates_archive(self, tmp_path, monkeypatch):
        """Force rotation by lowering the threshold to a tiny value.

        Note: archive naming is second-resolution, so a tight loop that
        triggers many rotations in a single second can have later archives
        overwrite earlier ones. The behaviour we lock down here is
        "rotation produces at least one valid gzip archive containing
        valid JSONL rows" — NOT "every record is preserved across the
        boundary". For production-scale rotation (one per ~50 MB), the
        second-resolution timestamp is plenty.
        """
        mod = _live_module()
        monkeypatch.setattr(mod, "ROTATION_THRESHOLD_BYTES", 1024)  # 1 KB
        monkeypatch.setattr(mod, "ROTATION_CHECK_EVERY_N_RECORDS", 5)

        ledger = mod.CostLedger(path=tmp_path / "ledger.jsonl")
        # Each record is ~250-300 bytes; 50 records = ~12-15 KB, well over 1 KB
        for i in range(50):
            ledger.record(**_make_record(parser_name=f"row_{i}"))

        archives = list(tmp_path.glob("cost_ledger.*.jsonl.gz"))
        assert len(archives) >= 1, "expected at least one rotated gzip archive"

        # Each archive must be a valid gzip and parse as JSONL
        for archive in archives:
            with gzip.open(archive, "rb") as f:
                archived = f.read().decode("utf-8")
            archived_lines = archived.splitlines()
            assert archived_lines, f"archive {archive.name} is empty"
            for line in archived_lines:
                row = json.loads(line)
                assert row["parser_name"].startswith("row_")

    def test_rotation_below_threshold_skips(self, tmp_path, monkeypatch):
        mod = _live_module()
        # Force a check on every write but keep the threshold high
        monkeypatch.setattr(mod, "ROTATION_THRESHOLD_BYTES", 100 * 1024 * 1024)
        monkeypatch.setattr(mod, "ROTATION_CHECK_EVERY_N_RECORDS", 1)
        ledger = mod.CostLedger(path=tmp_path / "ledger.jsonl")
        for i in range(10):
            ledger.record(**_make_record(parser_name=f"row_{i}"))
        archives = list(tmp_path.glob("cost_ledger.*.jsonl.gz"))
        assert archives == []

    def test_rotation_missing_portalocker_skips_quietly(
        self, tmp_path, monkeypatch
    ):
        """If portalocker is unavailable, rotation should warn and skip,
        NOT crash the record() call."""
        mod = _live_module()
        monkeypatch.setattr(mod, "ROTATION_THRESHOLD_BYTES", 100)
        monkeypatch.setattr(mod, "ROTATION_CHECK_EVERY_N_RECORDS", 1)

        # Hide portalocker from the rotation import
        import sys
        real_portalocker = sys.modules.pop("portalocker", None)
        sys.modules["portalocker"] = None  # type: ignore[assignment]
        try:
            ledger = mod.CostLedger(path=tmp_path / "ledger.jsonl")
            # Should NOT raise
            for i in range(5):
                ledger.record(**_make_record(parser_name=f"row_{i}"))
        finally:
            if real_portalocker is not None:
                sys.modules["portalocker"] = real_portalocker
            else:
                sys.modules.pop("portalocker", None)


# --------------------------------------------------------------------------- #
# _invoke_provider integration                                                #
# --------------------------------------------------------------------------- #


class TestInvokeProviderIntegration:
    """Verify _invoke_provider records both success and failure rows."""

    def _make_generator(self, provider_mock):
        """Construct a LuaGenerator with a fake provider.

        The provider mock must expose ``name`` (str) and a coroutine
        ``agenerate(...)``.
        """
        from components.lua_generator import LuaGenerator
        gen = LuaGenerator(provider=provider_mock)
        # Defang the system-prompt builder - it pulls in heavy harness
        # imports we don't need for this test.
        gen._build_system_prompt = lambda: "fake system prompt"  # type: ignore[method-assign]
        return gen

    def test_invoke_provider_records_success_row(self, monkeypatch, tmp_path):
        from components.llm_provider import LLMResponse
        import components.cost_ledger as cl

        # Reroute the module-level singleton to this test's tmp_path
        ledger_path = tmp_path / "ledger.jsonl"
        monkeypatch.setenv("COST_LEDGER_PATH", str(ledger_path))
        cl.set_default_ledger(None)
        try:
            # Build a fake provider whose agenerate returns a populated LLMResponse
            fake_resp = LLMResponse(
                text="-- generated lua --",
                model="claude-opus-4-7",
                usage={"input_tokens": 1234, "output_tokens": 567},
                cache_read_input_tokens=42,
                finish_reason="end_turn",
                provider="anthropic",
                cache_breakpoints_used=2,
                response_id="resp_xyz",
                thinking_tokens=128,
            )

            class FakeProvider:
                name = "anthropic"

                async def agenerate(self, **_kwargs):
                    return fake_resp

                @classmethod
                def _max_output_tokens_for(cls, model):
                    return 32000

            gen = self._make_generator(FakeProvider())
            result = gen._invoke_provider(
                messages=[{"role": "user", "content": "hello"}],
                model_override="claude-opus-4-7",
                max_tokens=8000,
                parser_name="cisco_duo",
                iteration=2,
            )
            assert result is fake_resp

            # One row recorded
            lines = ledger_path.read_text(encoding="utf-8").splitlines()
            assert len(lines) == 1
            row = json.loads(lines[0])
            assert row["parser_name"] == "cisco_duo"
            assert row["provider"] == "anthropic"
            assert row["model"] == "claude-opus-4-7"
            assert row["iteration"] == 2
            assert row["tokens_in"] == 1234
            assert row["tokens_out"] == 567
            assert row["cache_read"] == 42
            assert row["cache_breakpoints_used"] == 2
            assert row["response_id"] == "resp_xyz"
            assert row["thinking_tokens"] == 128
            assert row["finish_reason"] == "end_turn"
            assert row["latency_ms"] >= 0
            # No PII / Lua body
            assert "lua" not in row
            assert "text" not in row
        finally:
            cl.set_default_ledger(None)

    def test_invoke_provider_records_failure_row_and_reraises(
        self, monkeypatch, tmp_path
    ):
        import components.cost_ledger as cl

        ledger_path = tmp_path / "ledger.jsonl"
        monkeypatch.setenv("COST_LEDGER_PATH", str(ledger_path))
        cl.set_default_ledger(None)
        try:
            class _LLMProviderError(Exception):
                pass

            class FailingProvider:
                name = "openai"

                async def agenerate(self, **_kwargs):
                    raise _LLMProviderError("simulated 500")

                @classmethod
                def _max_output_tokens_for(cls, model):
                    return 16000

            gen = self._make_generator(FailingProvider())
            with pytest.raises(_LLMProviderError):
                gen._invoke_provider(
                    messages=[{"role": "user", "content": "hi"}],
                    model_override="gpt-5",
                    max_tokens=8000,
                    parser_name="okta",
                    iteration=1,
                )

            lines = ledger_path.read_text(encoding="utf-8").splitlines()
            assert len(lines) == 1
            row = json.loads(lines[0])
            assert row["parser_name"] == "okta"
            assert row["provider"] == "openai"
            assert row["model"] == "gpt-5"
            assert row["iteration"] == 1
            assert row["tokens_in"] == 0
            assert row["tokens_out"] == 0
            assert row["finish_reason"] == "_LLMProviderError"
            assert row["latency_ms"] >= 0
        finally:
            cl.set_default_ledger(None)

    def test_ledger_failure_does_not_block_call(self, monkeypatch, tmp_path):
        """A broken ledger must NEVER swallow or alter the provider call."""
        from components.llm_provider import LLMResponse
        import components.cost_ledger as cl

        fake_resp = LLMResponse(
            text="-- ok --",
            model="claude-opus-4-7",
            usage={"input_tokens": 10, "output_tokens": 5},
            provider="anthropic",
        )

        class FakeProvider:
            name = "anthropic"

            async def agenerate(self, **_kwargs):
                return fake_resp

            @classmethod
            def _max_output_tokens_for(cls, model):
                return 32000

        gen = self._make_generator(FakeProvider())

        # Inject a ledger whose record() always raises
        broken = MagicMock()
        broken.record.side_effect = OSError("disk full")
        cl.set_default_ledger(broken)
        try:
            # Should still return the LLMResponse
            result = gen._invoke_provider(
                messages=[{"role": "user", "content": "hi"}],
                model_override="claude-opus-4-7",
                max_tokens=8000,
                parser_name="anything",
                iteration=0,
            )
            assert result is fake_resp
            assert broken.record.called
        finally:
            cl.set_default_ledger(None)


# --------------------------------------------------------------------------- #
# Fix 1: _agenerate_fast records to ledger                                    #
# --------------------------------------------------------------------------- #


class TestAgenerateFastLedger:
    """FU17 round-2 (Fix 1): the daemon fast-path used to bypass
    ``_invoke_provider`` and produce zero cost rows. Verify a single row
    lands per fast-mode call with ``iteration=0`` (fast mode is single-shot).
    """

    def test_agenerate_fast_records_to_ledger(self, monkeypatch, tmp_path):
        import asyncio
        from components.lua_generator import (
            LuaGenerator,
            GenerationRequest,
            GenerationOptions,
        )
        from components.llm_provider import LLMResponse
        import components.cost_ledger as cl

        ledger_path = tmp_path / "ledger.jsonl"
        monkeypatch.setenv("COST_LEDGER_PATH", str(ledger_path))
        cl.set_default_ledger(None)
        try:
            fake_resp = LLMResponse(
                text=(
                    "```lua\nfunction processEvent(event) "
                    "return event end\n```"
                ),
                model="claude-haiku-4-5-20251001",
                usage={"input_tokens": 222, "output_tokens": 111},
                cache_read_input_tokens=33,
                finish_reason="end_turn",
                provider="anthropic",
                cache_breakpoints_used=1,
                response_id="resp_fast_001",
            )

            class FakeProvider:
                name = "anthropic"

                async def agenerate(self, **_kwargs):
                    return fake_resp

                @classmethod
                def _max_output_tokens_for(cls, model):
                    return 32000

            gen = LuaGenerator(provider=FakeProvider())
            # Defang heavy prompt builders we don't need for this test.
            gen._build_system_prompt = lambda: "fake system"  # type: ignore[method-assign]
            gen._build_user_prompt = lambda req: "fake user"  # type: ignore[method-assign]

            request = GenerationRequest(
                parser_id="cisco_duo_admin_001",
                parser_name="cisco_duo_admin",
                parser_analysis={},
                source_fields=[],
                vendor="cisco",
                product="duo",
            )
            opts = GenerationOptions(mode="fast")

            result = asyncio.run(gen.agenerate(request, opts))
            assert result is not None

            lines = ledger_path.read_text(encoding="utf-8").splitlines()
            assert len(lines) == 1, (
                f"expected exactly 1 cost row from fast-mode call, got {len(lines)}"
            )
            row = json.loads(lines[0])
            assert row["parser_name"] == "cisco_duo_admin"
            assert row["provider"] == "anthropic"
            assert row["iteration"] == 0  # fast mode is single-shot
            assert row["retry_attempt"] == 0
            assert row["tokens_in"] == 222
            assert row["tokens_out"] == 111
            assert row["cache_read"] == 33
            assert row["finish_reason"] == "end_turn"
            assert row["latency_ms"] >= 0
        finally:
            cl.set_default_ledger(None)

    def test_agenerate_fast_records_failure_row(self, monkeypatch, tmp_path):
        """Permanent provider error: must still record a failure row."""
        import asyncio
        from components.lua_generator import (
            LuaGenerator,
            GenerationRequest,
            GenerationOptions,
        )
        from components.llm_provider import LLMProviderPermanentError
        import components.cost_ledger as cl

        ledger_path = tmp_path / "ledger.jsonl"
        monkeypatch.setenv("COST_LEDGER_PATH", str(ledger_path))
        cl.set_default_ledger(None)
        try:
            class FailingProvider:
                name = "anthropic"

                async def agenerate(self, **_kwargs):
                    raise LLMProviderPermanentError("api key invalid")

                @classmethod
                def _max_output_tokens_for(cls, model):
                    return 32000

            gen = LuaGenerator(provider=FailingProvider())
            gen._build_system_prompt = lambda: "fake system"  # type: ignore[method-assign]
            gen._build_user_prompt = lambda req: "fake user"  # type: ignore[method-assign]

            request = GenerationRequest(
                parser_id="okta_001",
                parser_name="okta",
                parser_analysis={},
                source_fields=[],
                vendor="okta",
                product="okta",
            )
            opts = GenerationOptions(mode="fast")

            result = asyncio.run(gen.agenerate(request, opts))
            # _agenerate_fast returns a failure result rather than raising
            assert result is not None
            assert result.success is False

            lines = ledger_path.read_text(encoding="utf-8").splitlines()
            assert len(lines) == 1
            row = json.loads(lines[0])
            assert row["parser_name"] == "okta"
            assert row["tokens_in"] == 0
            assert row["tokens_out"] == 0
            assert row["finish_reason"] == "LLMProviderPermanentError"
        finally:
            cl.set_default_ledger(None)


# --------------------------------------------------------------------------- #
# Fix 2: GPT-5 strategy SDK adapter records to ledger                         #
# --------------------------------------------------------------------------- #


class TestGpt5StrategyLedger:
    """FU17 round-2 (Fix 2): the GPT-5 plan/code/refine chain runs via
    ``_call_openai_responses_via_sdk``, which used to bypass the cost
    ledger entirely. Verify each provider call records one row with the
    expected ``iteration`` step number.
    """

    def test_gpt5_adapter_records_each_call_to_ledger(
        self, monkeypatch, tmp_path
    ):
        from components.agentic_lua_generator import AgenticLuaGenerator
        from components.llm_provider import LLMResponse
        import components.cost_ledger as cl

        ledger_path = tmp_path / "ledger.jsonl"
        monkeypatch.setenv("COST_LEDGER_PATH", str(ledger_path))
        cl.set_default_ledger(None)
        try:
            fake_resp = LLMResponse(
                text="-- fake gpt-5 output --",
                model="gpt-5",
                usage={"input_tokens": 200, "output_tokens": 100},
                cache_read_input_tokens=0,
                finish_reason="stop",
                provider="openai",
                response_id="resp_gpt5_xyz",
            )

            class FakeOpenAIProvider:
                name = "openai"

                def generate(self, **_kwargs):
                    return fake_resp

            shim = AgenticLuaGenerator(api_key="x", provider="openai")
            # Inject the fake OpenAI provider into the inner LuaGenerator.
            shim._inner._provider_override = FakeOpenAIProvider()

            # Three back-to-back calls representing plan, code, refinement.
            for iter_num in (0, 1, 2):
                shim._call_openai_responses_via_sdk(
                    model="gpt-5",
                    instructions="sys",
                    input_items=[{"role": "user", "content": "x"}],
                    parser_name="okta",
                    iteration=iter_num,
                )

            lines = ledger_path.read_text(encoding="utf-8").splitlines()
            assert len(lines) == 3, (
                f"expected 3 cost rows from gpt5 plan/code/refine, got {len(lines)}"
            )
            iterations = [json.loads(line)["iteration"] for line in lines]
            assert iterations == [0, 1, 2]
            for line in lines:
                row = json.loads(line)
                assert row["parser_name"] == "okta"
                assert row["provider"] == "openai"
                assert row["model"] == "gpt-5"
                assert row["tokens_in"] == 200
                assert row["tokens_out"] == 100
                assert row["finish_reason"] == "stop"
        finally:
            cl.set_default_ledger(None)

    def test_gpt5_adapter_records_failure_row(self, monkeypatch, tmp_path):
        """Provider raises -> failure row recorded, adapter still returns
        the existing ``{"text": None, ...}`` shape (does NOT re-raise)."""
        from components.agentic_lua_generator import AgenticLuaGenerator
        import components.cost_ledger as cl

        ledger_path = tmp_path / "ledger.jsonl"
        monkeypatch.setenv("COST_LEDGER_PATH", str(ledger_path))
        cl.set_default_ledger(None)
        try:
            class _OpenAIBoom(Exception):
                pass

            class FailingProvider:
                name = "openai"

                def generate(self, **_kwargs):
                    raise _OpenAIBoom("simulated 503")

            shim = AgenticLuaGenerator(api_key="x", provider="openai")
            shim._inner._provider_override = FailingProvider()

            result = shim._call_openai_responses_via_sdk(
                model="gpt-5",
                instructions="sys",
                input_items=[{"role": "user", "content": "x"}],
                parser_name="okta",
                iteration=0,
            )
            # Existing contract preserved — caller gets None fields, no exception
            assert result == {"text": None, "response_id": None, "data": None}

            lines = ledger_path.read_text(encoding="utf-8").splitlines()
            assert len(lines) == 1
            row = json.loads(lines[0])
            assert row["provider"] == "openai"
            assert row["finish_reason"] == "_OpenAIBoom"
            assert row["tokens_in"] == 0
            assert row["tokens_out"] == 0
        finally:
            cl.set_default_ledger(None)


# --------------------------------------------------------------------------- #
# Fix 3: truncation retry produces 2 rows with distinct retry_attempt         #
# --------------------------------------------------------------------------- #


class TestTruncationRetryLedger:
    """FU17 round-2 (Fix 3): ``_call_llm`` retries once on truncation by
    calling ``_invoke_provider`` again with a bumped ``max_tokens`` ceiling.
    Both calls land in the ledger; the ``retry_attempt`` field
    disambiguates them (0 = first attempt, 1 = post-truncation retry).
    """

    def test_truncation_retry_records_two_rows_with_distinct_retry_attempt(
        self, monkeypatch, tmp_path
    ):
        from components.lua_generator import LuaGenerator
        from components.llm_provider import LLMResponse
        import components.cost_ledger as cl

        ledger_path = tmp_path / "ledger.jsonl"
        monkeypatch.setenv("COST_LEDGER_PATH", str(ledger_path))
        cl.set_default_ledger(None)
        try:
            # First response: truncated (finish_reason="max_tokens" for Anthropic).
            # Second response: full (finish_reason="end_turn").
            truncated_resp = LLMResponse(
                text="-- partial --",
                model="claude-opus-4-7",
                usage={"input_tokens": 50, "output_tokens": 8000},
                finish_reason="max_tokens",
                provider="anthropic",
            )
            full_resp = LLMResponse(
                text="-- full output --",
                model="claude-opus-4-7",
                usage={"input_tokens": 50, "output_tokens": 1500},
                finish_reason="end_turn",
                provider="anthropic",
            )

            responses = [truncated_resp, full_resp]

            class TruncThenFullProvider:
                name = "anthropic"

                async def agenerate(self, **_kwargs):
                    return responses.pop(0)

                @classmethod
                def _max_output_tokens_for(cls, model):
                    return 32000

            gen = LuaGenerator(provider=TruncThenFullProvider())
            gen._build_system_prompt = lambda: "sys"  # type: ignore[method-assign]

            text = gen._call_llm(
                messages=[{"role": "user", "content": "hi"}],
                model_override="claude-opus-4-7",
                parser_name="cisco_duo",
                iteration=2,
            )
            assert text == "-- full output --"

            lines = ledger_path.read_text(encoding="utf-8").splitlines()
            assert len(lines) == 2, (
                f"expected 2 rows (truncation + retry), got {len(lines)}"
            )
            row0 = json.loads(lines[0])
            row1 = json.loads(lines[1])
            assert row0["retry_attempt"] == 0
            assert row1["retry_attempt"] == 1
            assert row0["finish_reason"] == "max_tokens"
            assert row1["finish_reason"] == "end_turn"
            # Both rows carry the same logical user-visible iteration
            assert row0["iteration"] == row1["iteration"] == 2
            assert row0["parser_name"] == row1["parser_name"] == "cisco_duo"
        finally:
            cl.set_default_ledger(None)
