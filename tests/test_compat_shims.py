"""Phase 3.E shim attribute/method preservation tests."""
import inspect


class TestClaudeLuaGeneratorShimAttributes:
    def test_constructor_takes_config(self):
        from components.lua_generator import ClaudeLuaGenerator
        g = ClaudeLuaGenerator({"anthropic": {"api_key": "test"}})
        assert g is not None

    def test_has_generate_lua_method(self):
        from components.lua_generator import ClaudeLuaGenerator
        assert hasattr(ClaudeLuaGenerator, "generate_lua")

    def test_has_batch_generate_lua_method(self):
        from components.lua_generator import ClaudeLuaGenerator
        assert hasattr(ClaudeLuaGenerator, "batch_generate_lua")


class TestAgenticLuaGeneratorShimAttributes:
    def test_constructor_full_signature(self):
        from components.agentic_lua_generator import AgenticLuaGenerator
        g = AgenticLuaGenerator(
            api_key="test",
            model="claude-haiku-4-5-20251001",
            provider="anthropic",
            max_output_tokens=4000,
            max_iterations=3,
        )
        assert g is not None

    def test_has_generate_method(self):
        from components.agentic_lua_generator import AgenticLuaGenerator
        assert hasattr(AgenticLuaGenerator, "generate")

    def test_generate_takes_parser_entry_and_force_regenerate(self):
        from components.agentic_lua_generator import AgenticLuaGenerator
        sig = inspect.signature(AgenticLuaGenerator.generate)
        params = list(sig.parameters.keys())
        assert "parser_entry" in params
        assert "force_regenerate" in params


class TestModuleImports:
    def test_components_reexports_ClaudeLuaGenerator(self):
        from components import ClaudeLuaGenerator
        assert ClaudeLuaGenerator is not None

    def test_components_reexports_LuaGenerationResult(self):
        from components import LuaGenerationResult
        assert LuaGenerationResult is not None
