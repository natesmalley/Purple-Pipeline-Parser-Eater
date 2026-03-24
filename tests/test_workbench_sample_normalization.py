from components.web_ui.workbench_jobs import normalize_text_samples, parse_sample_to_event


def test_normalize_text_samples_strips_markdown_fences_and_splits_separator():
    raw = """```json
{"vendor":"okta","eventType":"user.session.start"}
---
{"vendor":"okta","eventType":"user.authentication.auth_via_mfa"}
```"""
    got = normalize_text_samples(raw)
    assert len(got) == 2
    assert got[0].startswith("{")
    assert "okta" in got[0]
    assert "auth_via_mfa" in got[1]


def test_normalize_text_samples_splits_concatenated_json_objects():
    raw = '{"vendor":"okta","eventType":"user.session.start"}\n{"vendor":"okta","eventType":"user.session.end"}'
    got = normalize_text_samples(raw)
    assert len(got) == 2
    assert "session.start" in got[0]
    assert "session.end" in got[1]


def test_normalize_text_samples_normalizes_smart_quotes():
    raw = '{“vendor”:“okta”,“eventType”:“user.session.start”}'
    got = normalize_text_samples(raw)
    assert len(got) == 1
    assert got[0] == '{"vendor":"okta","eventType":"user.session.start"}'


def test_parse_sample_to_event_returns_dict_for_valid_json():
    sample = '{"vendor":"okta","eventType":"user.session.start"}'
    parsed = parse_sample_to_event(sample)
    assert isinstance(parsed, dict)
    assert parsed["vendor"] == "okta"


def test_parse_sample_to_event_keeps_raw_when_invalid_json():
    sample = '{"vendor":"okta"'
    parsed = parse_sample_to_event(sample)
    assert isinstance(parsed, str)
    assert parsed == sample
