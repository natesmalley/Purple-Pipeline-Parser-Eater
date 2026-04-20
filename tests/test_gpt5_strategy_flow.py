from pathlib import Path

from components.agentic_lua_generator import AgenticLuaGenerator, GPT5_PLAN_SCHEMA


class _HarnessStub:
    def run_all_checks(self, lua_code, parser_config, ocsf_version="1.3.0"):
        return {
            "confidence_score": 84,
            "confidence_grade": "B",
            "checks": {
                "field_comparison": {"coverage_pct": 85},
                "lua_linting": {"issues": []},
                "ocsf_mapping": {"missing_required": [], "class_uid": 4003, "class_name": "DNS Activity"},
            },
            "ocsf_alignment": {"required_coverage": 100.0},
        }


class _SourceStub:
    def analyze_parser(self, parser_entry):
        return {"fields": [{"name": "message", "type": "string"}]}


class _GPT5FlowGenerator(AgenticLuaGenerator):
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
                "instructions": instructions,
                "input_items": input_items,
                "previous_response_id": previous_response_id,
                "response_format": response_format,
            }
        )
        if response_format:
            return {
                "text": (
                    '{"class_uid":4003,"class_name":"DNS Activity","category_uid":4,'
                    '"category_name":"Network Activity","activity_id":1,"activity_name":"DNS Query",'
                    '"timestamp_sources":["timestamp"],"severity_strategy":"default 0",'
                    '"embedded_payload_strategy":"parse message kv",'
                    '"mappings":[{"target":"src_endpoint.ip","source_candidates":["cliIP"],"transform":"direct","required":false}],'
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


def test_gpt5_strategy_uses_planner_and_previous_response_id(tmp_path: Path):
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

    result = gen.generate(
        {
            "parser_name": "akamai_dns-latest",
            "ingestion_mode": "push",
            "raw_examples": [{"message": 'AkamaiDNS cliIP="1.2.3.4" domain="example.com"'}],
            "config": {"attributes": {"dataSource": {"vendor": "Akamai", "product": "DNS"}}},
        },
        force_regenerate=True,
    )

    assert len(gen.calls) == 2
    assert gen.calls[0]["response_format"]["schema"] == GPT5_PLAN_SCHEMA
    assert gen.calls[1]["previous_response_id"] == "resp_plan"
    assert result["generation_method"] == "agentic_llm_gpt5_plan"
    assert result["confidence_score"] == 84


def test_gpt5_plan_schema_requires_all_declared_top_level_properties():
    assert sorted(GPT5_PLAN_SCHEMA["required"]) == sorted(GPT5_PLAN_SCHEMA["properties"].keys())
