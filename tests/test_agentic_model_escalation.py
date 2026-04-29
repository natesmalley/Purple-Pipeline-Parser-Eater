from pathlib import Path

import pytest

from components.agentic_lua_generator import AgenticLuaGenerator


class _HarnessStub:
    def run_all_checks(self, lua_code, parser_config, ocsf_version="1.3.0", custom_test_events=None):
        if "STRONG_MODEL" in lua_code:
            return {
                "confidence_score": 91,
                "confidence_grade": "A",
                "checks": {"lua_linting": {"issues": []}, "ocsf_mapping": {"missing_required": []}},
            }
        return {
            "confidence_score": 62,
            "confidence_grade": "D",
            "checks": {"lua_linting": {"issues": []}, "ocsf_mapping": {"missing_required": ["activity_id"]}},
        }


class _SourceStub:
    def analyze_parser(self, parser_entry):
        return {"fields": []}


class _EscalatingGenerator(AgenticLuaGenerator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.models_seen = []

    @staticmethod
    def _is_gpt5_family(model: str) -> bool:
        return False

    def _call_llm(self, messages, model_override=None):
        model = model_override or self.model
        self.models_seen.append(model)
        if "gpt-5.2" in model:
            return "function processEvent(event)\n  -- STRONG_MODEL\n  return event\nend"
        return "function processEvent(event)\n  return event\nend"


def _parser_entry():
    return {
        "parser_name": "test_parser",
        "ingestion_mode": "push",
        "config": {"attributes": {"dataSource": {"vendor": "acme", "product": "auth"}}},
    }


def test_escalates_from_mini_to_stronger_model(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_STRONG_MODEL", "gpt-5.2")
    gen = _EscalatingGenerator(
        api_key="test-key",
        model="gpt-4o-mini",
        provider="openai",
        max_iterations=1,
        score_threshold=80,
        output_dir=tmp_path,
    )
    gen.harness = _HarnessStub()
    gen.source_analyzer = _SourceStub()

    result = gen.generate(_parser_entry(), force_regenerate=True)

    assert gen.models_seen == ["gpt-4o-mini", "gpt-5.2"]
    assert result["confidence_score"] == 91
    assert result["model"] == "gpt-5.2"
    assert result["quality"] == "accepted"


def test_no_escalation_when_primary_model_already_strong(tmp_path: Path):
    gen = _EscalatingGenerator(
        api_key="test-key",
        model="gpt-5.2",
        provider="openai",
        max_iterations=1,
        score_threshold=80,
        output_dir=tmp_path,
    )
    gen.harness = _HarnessStub()
    gen.source_analyzer = _SourceStub()

    result = gen.generate(_parser_entry(), force_regenerate=True)

    assert gen.models_seen == ["gpt-5.2"]
    assert result["confidence_score"] == 91
    assert result["model"] == "gpt-5.2"


def test_no_implicit_escalation_without_strong_model_env(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_STRONG_MODEL", raising=False)
    gen = _EscalatingGenerator(
        api_key="test-key",
        model="gpt-4o-mini",
        provider="openai",
        max_iterations=1,
        score_threshold=80,
        output_dir=tmp_path,
    )
    gen.harness = _HarnessStub()
    gen.source_analyzer = _SourceStub()

    result = gen.generate(_parser_entry(), force_regenerate=True)

    assert gen.models_seen == ["gpt-4o-mini"]
    assert result["model"] == "gpt-4o-mini"
    assert result["quality"] == "below_threshold"


# ---------------------------------------------------------------------------
# Gemini provider branch tests
# ---------------------------------------------------------------------------


class _GeminiEscalatingGenerator(AgenticLuaGenerator):
    """Stub that records models seen and returns canned Lua for Gemini."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.models_seen = []

    def _call_llm(self, messages, model_override=None):
        model = model_override or self.model
        self.models_seen.append(model)
        if "gemini-3.1-pro" in model:
            return "function processEvent(event)\n  -- STRONG_MODEL\n  return event\nend"
        return "function processEvent(event)\n  return event\nend"


def test_gemini_provider_instantiates(tmp_path: Path):
    """Setting provider='gemini' should construct the generator without error."""
    gen = _GeminiEscalatingGenerator(
        api_key="test-gemini-key",
        model="gemini-3.1-flash-lite",
        provider="gemini",
        max_iterations=1,
        score_threshold=80,
        output_dir=tmp_path,
    )
    assert gen.provider == "gemini"
    assert gen.model == "gemini-3.1-flash-lite"


def test_gemini_escalation_to_strong_model(tmp_path: Path, monkeypatch):
    """Gemini should escalate from flash-lite to pro via GEMINI_STRONG_MODEL."""
    monkeypatch.setenv("GEMINI_STRONG_MODEL", "gemini-3.1-pro")
    gen = _GeminiEscalatingGenerator(
        api_key="test-gemini-key",
        model="gemini-3.1-flash-lite",
        provider="gemini",
        max_iterations=1,
        score_threshold=80,
        output_dir=tmp_path,
    )
    gen.harness = _HarnessStub()
    gen.source_analyzer = _SourceStub()

    result = gen.generate(_parser_entry(), force_regenerate=True)

    assert gen.models_seen == ["gemini-3.1-flash-lite", "gemini-3.1-pro"]
    assert result["confidence_score"] == 91
    assert result["model"] == "gemini-3.1-pro"
    assert result["quality"] == "accepted"


def test_gemini_no_escalation_without_strong_model_env(tmp_path: Path, monkeypatch):
    """Without GEMINI_STRONG_MODEL, Gemini should not escalate."""
    monkeypatch.delenv("GEMINI_STRONG_MODEL", raising=False)
    gen = _GeminiEscalatingGenerator(
        api_key="test-gemini-key",
        model="gemini-3.1-flash-lite",
        provider="gemini",
        max_iterations=1,
        score_threshold=80,
        output_dir=tmp_path,
    )
    gen.harness = _HarnessStub()
    gen.source_analyzer = _SourceStub()

    result = gen.generate(_parser_entry(), force_regenerate=True)

    assert gen.models_seen == ["gemini-3.1-flash-lite"]
    assert result["model"] == "gemini-3.1-flash-lite"
    assert result["quality"] == "below_threshold"


def test_unknown_provider_raises_valueerror(tmp_path: Path):
    """An unknown provider string should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        AgenticLuaGenerator(
            api_key="test-key",
            model="some-model",
            provider="deepseek",
            output_dir=tmp_path,
        )
