from components.agentic_lua_generator import SYSTEM_PROMPT, build_generation_prompt


def test_system_prompt_contains_observo_runtime_safety_rules():
    assert "function processEvent(event)" in SYSTEM_PROMPT
    assert "Do NOT use `event:get(...)" in SYSTEM_PROMPT
    assert "Do NOT rely on external modules or `require(...)` calls" in SYSTEM_PROMPT
    assert "Wrap transformation logic in `pcall`" in SYSTEM_PROMPT
    assert "Define every helper you call ABOVE `processEvent`" in SYSTEM_PROMPT


def test_generation_prompt_repeats_critical_compatibility_requirements():
    prompt = build_generation_prompt(
        parser_name="test_parser",
        vendor="acme",
        product="widget",
        class_uid=3002,
        class_name="Authentication",
        ocsf_fields={
            "category_uid": 3,
            "category_name": "Identity & Access Management",
            "required_fields": ["class_uid", "category_uid", "activity_id", "time", "type_uid", "severity_id"],
            "optional_fields": ["actor.user.name"],
        },
        source_fields=[{"name": "timestamp", "type": "string"}],
        ingestion_mode="push",
        examples=[{"timestamp": "2026-01-01T00:00:00Z"}],
    )
    assert "Never use `event:get(...)` or `event:set(...)`" in prompt
    assert "Define all helper functions above `processEvent`" in prompt
    assert "Wrap main transform logic in `pcall`" in prompt
    assert "os.time({..." in prompt
    assert "os.date(...)" in prompt
    assert "`pcall`" in prompt
