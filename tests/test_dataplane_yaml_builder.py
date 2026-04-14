"""Phase 5.A + 5.B tests for components.dataplane_yaml_builder.

Standalone dataplane YAML emitter - the sibling to the SaaS REST builder.
Tests cover:
- Snake_case key shape for lv3 v3 lua transforms
- Forbidden-key rejection (drop_on_error, bypass_transform, lua_script, etc.)
- Path sanitization for search_dirs (no /Users/, /home/*/, C:\\, ..)
- S1 HEC sink shape
- Pipeline assembly
"""
import pytest


class TestLv3V3LuaTransformShape:
    def test_basic_v3_shape(self):
        from components.dataplane_yaml_builder import build_lua_transform
        t = build_lua_transform(
            transform_id="test_tx",
            inputs=["src1"],
            lua_body="function process(event, emit) emit(event) end",
        )
        d = t.to_yaml_dict()
        assert d["type"] == "lua"
        assert d["version"] == "3"  # STRING, quoted
        assert d["inputs"] == ["src1"]
        assert d["parallelism"] == 1
        assert d["process"] == "process"
        assert "source" in d
        # NOT luaScript
        assert "luaScript" not in d
        # NOT lua_script either (binary rejects)
        assert "lua_script" not in d
        # NOT script (scol-only)
        assert "script" not in d

    def test_version_is_quoted_string(self):
        from components.dataplane_yaml_builder import build_lua_transform
        t = build_lua_transform("tx", ["s"], "body")
        assert isinstance(t.to_yaml_dict()["version"], str)

    def test_v2_fallback_shape(self):
        from components.dataplane_yaml_builder import build_lua_transform
        t = build_lua_transform("tx", ["s"], "body", version="2")
        d = t.to_yaml_dict()
        assert d["version"] == "2"
        assert "hooks" in d


class TestForbiddenKeys:
    @pytest.mark.parametrize("bad_key", [
        "drop_on_error", "drop_on_abort", "reroute_dropped",
        "bypass_transform", "metric_event",
        "lua_script", "script",
        "rpc_domain",
    ])
    def test_forbidden_keys_rejected(self, bad_key):
        from components.dataplane_yaml_builder import build_lua_transform, DataplaneYamlBuildError
        with pytest.raises(DataplaneYamlBuildError, match="forbidden"):
            build_lua_transform(
                "tx", ["s"], "body",
                extra_keys={bad_key: True},
            )


class TestSearchDirsSanitization:
    @pytest.mark.parametrize("bad_dir", [
        "/Users/alice/dev/lua",
        "/home/bob/lua",
        "C:\\Users\\carol\\lua",
        "/etc/dataplane/../secrets",
        "./../etc/dataplane",
    ])
    def test_bad_search_dirs_rejected(self, bad_dir):
        from components.dataplane_yaml_builder import build_lua_transform, DataplaneYamlBuildError
        with pytest.raises(DataplaneYamlBuildError, match="absolute developer path"):
            build_lua_transform("tx", ["s"], "body", search_dirs=[bad_dir])

    def test_default_search_dirs_from_env(self, monkeypatch):
        from components.dataplane_yaml_builder import build_lua_transform
        monkeypatch.setenv("OBSERVO_LUA_DIR", "/opt/ocsf")
        t = build_lua_transform("tx", ["s"], "body")
        d = t.to_yaml_dict()
        assert d["search_dirs"] == ["/opt/ocsf"]

    def test_default_search_dirs_fallback(self, monkeypatch):
        from components.dataplane_yaml_builder import build_lua_transform
        monkeypatch.delenv("OBSERVO_LUA_DIR", raising=False)
        t = build_lua_transform("tx", ["s"], "body")
        d = t.to_yaml_dict()
        assert d["search_dirs"] == ["/etc/dataplane/ocsf"]

    def test_clean_absolute_path_allowed(self):
        from components.dataplane_yaml_builder import build_lua_transform
        t = build_lua_transform("tx", ["s"], "body", search_dirs=["/etc/dataplane/ocsf"])
        d = t.to_yaml_dict()
        assert d["search_dirs"] == ["/etc/dataplane/ocsf"]


class TestSentinelOneHecSink:
    def test_basic_s1_hec_shape(self):
        from components.dataplane_yaml_builder import build_sentinelone_hec_sink
        s = build_sentinelone_hec_sink(
            sink_id="s1_out",
            inputs=["tx1"],
            endpoint="https://ingest.us-east-1.sentinelone.net:443",
            default_token="PLACEHOLDER_TOKEN_DO_NOT_COMMIT_REAL",
        )
        d = s.to_yaml_dict()
        assert d["type"] == "splunk_hec_logs"
        assert d["path"] == "/services/collector/event?isParsed=true"
        assert d["endpoint_target"] == "event"
        assert d["compression"] == "gzip"
        assert d["encoding"] == {"codec": "json", "json": {"pretty": False}}
        assert d["acknowledgements"] == {"enabled": False}
        assert d["batch"]["max_bytes"] == 6000000
        assert d["buffer"]["type"] == "memory"
        assert d["request"]["concurrency"] == "adaptive"

    def test_no_timestamp_key_default(self):
        """Plan 5.B: do NOT copy the production `timestamp_key: '""'` two-char bug."""
        from components.dataplane_yaml_builder import build_sentinelone_hec_sink
        s = build_sentinelone_hec_sink(
            "s1", ["tx"], "https://ingest.example.sentinelone.net:443", "PLACEHOLDER"
        )
        d = s.to_yaml_dict()
        assert "timestamp_key" not in d

    def test_http_endpoint_rejected(self):
        from components.dataplane_yaml_builder import build_sentinelone_hec_sink, DataplaneYamlBuildError
        with pytest.raises(DataplaneYamlBuildError, match="https"):
            build_sentinelone_hec_sink(
                "s1", ["tx"], "http://insecure.sentinelone.net", "PLACEHOLDER"
            )


class TestPipelineAssembly:
    def test_build_pipeline_yaml_top_level(self):
        from components.dataplane_yaml_builder import (
            build_lua_transform, build_sentinelone_hec_sink, build_pipeline_yaml,
        )
        t = build_lua_transform("ocsf", ["src1"], "body")
        s = build_sentinelone_hec_sink(
            "s1", ["ocsf"], "https://ingest.example.sentinelone.net:443", "PLACEHOLDER"
        )
        pipeline = build_pipeline_yaml([t], [s])
        assert "sources" in pipeline
        assert "transforms" in pipeline
        assert "sinks" in pipeline
        assert pipeline["transforms"]["ocsf"]["type"] == "lua"
        assert pipeline["sinks"]["s1"]["type"] == "splunk_hec_logs"

    def test_pipeline_has_no_forbidden_keys_top_level(self):
        from components.dataplane_yaml_builder import (
            build_lua_transform, build_sentinelone_hec_sink, build_pipeline_yaml,
        )
        t = build_lua_transform("ocsf", ["src1"], "body")
        s = build_sentinelone_hec_sink(
            "s1", ["ocsf"], "https://ingest.example.sentinelone.net:443", "PLACEHOLDER"
        )
        pipeline = build_pipeline_yaml([t], [s])
        # Flatten and check for forbidden keys at ANY level
        import json
        serialized = json.dumps(pipeline)
        for forbidden in ("drop_on_error", "drop_on_abort", "reroute_dropped",
                          "bypass_transform", "rpc_domain"):
            assert forbidden not in serialized, (
                f"Forbidden key {forbidden!r} leaked into pipeline output"
            )


class TestImportIsLight:
    def test_module_import_no_heavy_deps(self):
        import sys
        # Pre-reset
        for name in list(sys.modules):
            if name.startswith("components.dataplane_yaml_builder"):
                del sys.modules[name]
        import components.dataplane_yaml_builder  # noqa: F401
        heavy = [m for m in ("aiohttp", "anthropic", "yaml", "openai", "google.generativeai") if m in sys.modules]
        assert heavy == [], f"dataplane_yaml_builder.py leaked heavy deps at module load: {heavy}"
