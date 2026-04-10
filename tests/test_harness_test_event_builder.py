"""Unit tests for TestEventBuilder — synthetic test event generation."""

import pytest

from components.testing_harness.test_event_builder import TestEventBuilder


@pytest.fixture
def builder():
    return TestEventBuilder()


@pytest.fixture
def sample_parser_info():
    return {
        "parser_name": "test_parser",
        "vendor": "Acme",
        "product": "Firewall",
        "fields": [
            {"name": "src_ip", "type": "string"},
            {"name": "dst_ip", "type": "string"},
            {"name": "action", "type": "string"},
            {"name": "bytes_sent", "type": "integer"},
            {"name": "timestamp", "type": "datetime"},
        ],
    }


class TestBuildEvents:

    def test_returns_four_events(self, builder, sample_parser_info):
        events = builder.build_events(sample_parser_info)
        assert len(events) == 4

    def test_each_event_has_required_keys(self, builder, sample_parser_info):
        events = builder.build_events(sample_parser_info)
        for ev in events:
            assert "name" in ev
            assert "description" in ev
            assert "event" in ev
            assert "expected_behavior" in ev

    def test_events_are_dicts(self, builder, sample_parser_info):
        events = builder.build_events(sample_parser_info)
        for ev in events:
            assert isinstance(ev["event"], dict)
            assert len(ev["event"]) > 0

    def test_event_names_distinct(self, builder, sample_parser_info):
        events = builder.build_events(sample_parser_info)
        names = [ev["name"] for ev in events]
        assert len(set(names)) == 4

    def test_happy_path_has_all_fields(self, builder, sample_parser_info):
        events = builder.build_events(sample_parser_info)
        happy = events[0]
        field_names = {f["name"] for f in sample_parser_info["fields"]}
        for name in field_names:
            assert name in happy["event"], f"Happy path missing field: {name}"

    def test_empty_fields(self, builder):
        info = {"parser_name": "empty", "vendor": "X", "product": "Y", "fields": []}
        events = builder.build_events(info)
        assert len(events) == 4
        for ev in events:
            assert isinstance(ev["event"], dict)


class TestBuildCustomEvent:

    def test_wraps_dict(self, builder):
        data = {"src_ip": "10.0.0.1", "action": "allow"}
        result = builder.build_custom_event(data)
        assert result["event"] == data
        assert result["name"] == "Custom Event"
