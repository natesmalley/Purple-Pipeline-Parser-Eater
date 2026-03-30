from pathlib import Path

from components.agentic_lua_generator import AgenticLuaGenerator


class _HarnessStub:
    def run_all_checks(self, lua_code, parser_config, ocsf_version="1.3.0"):
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


def test_escalates_from_mini_to_stronger_model(tmp_path: Path):
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
