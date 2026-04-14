"""Phase 3.D + 3.E unified LuaGenerator tests."""
import asyncio

import pytest


class TestGenerationRequestAdapters:
    def test_from_legacy_args_basic(self):
        from components.lua_generator import GenerationRequest
        req = GenerationRequest.from_legacy_args(
            "test_parser",
            {
                "parser_name": "Test Parser",
                "source_fields": [{"name": "src_ip", "type": "string"}],
                "ocsf_classification": {"class_uid": 4001},
                "vendor": "Vendor", "product": "Product",
            },
        )
        assert req.parser_id == "test_parser"
        assert req.parser_name == "Test Parser"
        assert len(req.source_fields) == 1
        assert req.source_fields[0].name == "src_ip"
        assert req.source_fields[0].type == "string"
        assert req.ocsf_class_uid == 4001
        assert req.vendor == "Vendor"

    def test_from_legacy_args_derives_parser_name(self):
        from components.lua_generator import GenerationRequest
        req = GenerationRequest.from_legacy_args("bare_id", {})
        assert req.parser_name == "bare_id"

    def test_from_legacy_args_with_ocsf_schema(self):
        from components.lua_generator import GenerationRequest
        req = GenerationRequest.from_legacy_args("p", {}, ocsf_schema={"class_uid": 2001})
        assert req.ocsf_schema == {"class_uid": 2001}

    def test_from_legacy_args_string_source_fields(self):
        from components.lua_generator import GenerationRequest
        req = GenerationRequest.from_legacy_args("p", {"source_fields": ["src_ip", "dest_ip"]})
        assert [sf.name for sf in req.source_fields] == ["src_ip", "dest_ip"]

    def test_from_workbench_entry(self):
        from components.lua_generator import GenerationRequest
        req = GenerationRequest.from_workbench_entry({
            "parser_id": "w1",
            "parser_name": "W1",
            "source_fields": [{"name": "a", "type": "int"}],
            "raw_examples": ["{\"a\":1}", "{\"a\":2}"],
            "historical_examples": [{"a": 3}],
        })
        assert req.parser_id == "w1"
        assert req.parser_name == "W1"
        assert len(req.raw_examples) == 2
        assert len(req.historical_examples) == 1

    def test_test_events_is_merged_dedup(self):
        from components.lua_generator import GenerationRequest
        req = GenerationRequest.from_workbench_entry({
            "parser_id": "p", "parser_name": "p",
            "raw_examples": ["a", "b", "a"],
            "historical_examples": ["b", "c"],
        })
        assert req.test_events == ["a", "b", "c"]


class TestGenerationResultFacade:
    def test_attribute_access(self):
        from components.lua_generator import GenerationResult
        r = GenerationResult(parser_id="p", parser_name="p", lua_code="")
        assert r.parser_id == "p"
        assert r.lua_code == ""

    def test_mapping_getitem(self):
        from components.lua_generator import GenerationResult
        r = GenerationResult(parser_id="p", parser_name="p", lua_code="", model="m")
        assert r["model"] == "m"

    def test_mapping_get(self):
        from components.lua_generator import GenerationResult
        r = GenerationResult(parser_id="p", parser_name="p", lua_code="")
        assert r.get("ingestion_mode") == ""
        assert r.get("missing", "default") == "default"

    def test_mapping_contains(self):
        from components.lua_generator import GenerationResult
        r = GenerationResult(parser_id="p", parser_name="p", lua_code="")
        assert "error" in r
        assert "nonexistent" not in r

    def test_mapping_keys_items(self):
        from components.lua_generator import GenerationResult
        r = GenerationResult(parser_id="p", parser_name="p", lua_code="")
        keys = list(r.keys())
        assert "parser_id" in keys
        assert "parser_name" in keys
        assert "harness_report" in keys
        items = dict(r.items())
        assert items["parser_id"] == "p"

    def test_quality_is_string_not_dict(self):
        from components.lua_generator import GenerationResult
        r = GenerationResult(parser_id="p", parser_name="p", lua_code="x")
        assert isinstance(r.quality, str)
        assert r.quality in ("accepted", "below_threshold")

    def test_test_cases_is_string_not_list(self):
        from components.lua_generator import GenerationResult
        r = GenerationResult(parser_id="p", parser_name="p", lua_code="x")
        assert isinstance(r.test_cases, str)

    def test_to_dict_round_trip(self):
        from components.lua_generator import GenerationResult
        r = GenerationResult(parser_id="p", parser_name="p", lua_code="x", model="m")
        d = r.to_dict()
        assert d["parser_id"] == "p"
        assert d["model"] == "m"
        assert "request" not in d
        assert "options" not in d


class TestLuaGeneratorModes:
    def test_sync_generate_in_running_loop_raises(self):
        from components.lua_generator import (
            LuaGenerator, GenerationRequest, GenerationOptions,
        )

        async def caller():
            g = LuaGenerator({})
            req = GenerationRequest.from_legacy_args("p", {})
            with pytest.raises(RuntimeError, match="running event loop"):
                g.generate(req, GenerationOptions(mode="fast"))

        asyncio.run(caller())

    def test_sync_generate_outside_loop_ok(self):
        from components.lua_generator import (
            LuaGenerator, GenerationRequest, GenerationOptions, GenerationResult,
        )

        g = LuaGenerator({})

        async def fake_agenerate(req, opts):
            return GenerationResult(
                parser_id=req.parser_id,
                parser_name=req.parser_name,
                lua_code="fake",
                success=True,
            )

        g.agenerate = fake_agenerate
        req = GenerationRequest.from_legacy_args("p", {})
        result = g.generate(req, GenerationOptions(mode="fast"))
        assert result.lua_code == "fake"


class TestClaudeLuaGeneratorShim:
    def test_shim_preserves_import_path(self):
        from components.lua_generator import ClaudeLuaGenerator, LuaGenerationResult
        assert ClaudeLuaGenerator is not None
        assert LuaGenerationResult is not None

    def test_shim_generate_lua_returns_compat_result(self):
        from components.lua_generator import ClaudeLuaGenerator, GenerationResult

        g = ClaudeLuaGenerator({})

        async def fake_inner(req, opts):
            return GenerationResult(
                parser_id=req.parser_id,
                parser_name=req.parser_name,
                lua_code="legacy_ok",
            )

        g._inner.agenerate = fake_inner

        async def run():
            return await g.generate_lua("test_id", {"parser_name": "Test"})

        result = asyncio.run(run())
        assert result.parser_id == "test_id"
        assert result.lua_code == "legacy_ok"
        assert "model" in result

    def test_shim_batch_success_only(self):
        from components.lua_generator import ClaudeLuaGenerator, GenerationResult

        g = ClaudeLuaGenerator({})

        async def fake_inner_batch(requests, opts):
            return [
                GenerationResult(parser_id="ok1", parser_name="ok1", lua_code="a", success=True),
                GenerationResult(parser_id="fail1", parser_name="fail1", lua_code="", success=False, error="nope"),
                GenerationResult(parser_id="ok2", parser_name="ok2", lua_code="b", success=True),
            ]

        g._inner.batch_generate_lua = fake_inner_batch

        async def run():
            return await g.batch_generate_lua(
                [{"parser_id": "ok1"}, {"parser_id": "fail1"}, {"parser_id": "ok2"}]
            )

        results = asyncio.run(run())
        assert len(results) == 2
        assert all(r.success for r in results)
