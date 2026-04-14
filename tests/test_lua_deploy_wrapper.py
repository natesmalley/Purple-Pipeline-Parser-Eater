"""Phase 2.A + 2.B tests for components.lua_deploy_wrapper.wrap_for_observo."""
import pytest

from components.lua_deploy_wrapper import wrap_for_observo


class TestWrapForObservoShape:
    def test_wrapped_contains_inner_processEvent(self):
        body = "function processEvent(event)\n  return event\nend"
        wrapped = wrap_for_observo(body)
        assert "function processEvent(event)" in wrapped

    def test_wrapped_contains_outer_process(self):
        body = "function processEvent(event)\n  return event\nend"
        wrapped = wrap_for_observo(body)
        assert "function process(event, emit)" in wrapped

    def test_outer_process_calls_processEvent(self):
        body = "function processEvent(event)\n  return event\nend"
        wrapped = wrap_for_observo(body)
        assert "processEvent(" in wrapped
        assert "out = processEvent" in wrapped or "local out = processEvent" in wrapped

    def test_helpers_are_prepended_by_default(self):
        """2.B: ocsf_helpers.lua contents must be inlined."""
        body = "function processEvent(event)\n  return event\nend"
        wrapped = wrap_for_observo(body)
        assert "function getNestedField" in wrapped or "function setNestedField" in wrapped

    def test_helpers_can_be_excluded(self):
        body = "function processEvent(event)\n  return event\nend"
        wrapped = wrap_for_observo(body, include_helpers=False)
        assert "function getNestedField" not in wrapped
        assert "function setNestedField" not in wrapped
        assert "function process(event, emit)" in wrapped  # outer still there

    def test_helpers_appear_before_processEvent(self):
        body = "function processEvent(event)\n  return event\nend"
        wrapped = wrap_for_observo(body)
        helpers_idx = wrapped.find("function getNestedField")
        process_event_idx = wrapped.find("function processEvent(event)")
        outer_idx = wrapped.find("function process(event, emit)")
        assert helpers_idx != -1
        assert process_event_idx != -1
        assert outer_idx != -1
        assert helpers_idx < process_event_idx < outer_idx, \
            "Expected order: helpers, then processEvent, then outer process"


class TestWrapForObservoIdempotence:
    def test_double_wrap_detected(self):
        """Wrapping an already-wrapped script must raise — never produce nested process()."""
        body = "function processEvent(event)\n  return event\nend"
        once = wrap_for_observo(body)
        with pytest.raises(ValueError, match="already wrapped"):
            wrap_for_observo(once)


class TestWrapPreservesAuthoringContract:
    """2.A: the raw authored contract is processEvent. Only the deploy path adds outer process."""

    def test_raw_body_does_not_contain_outer_process(self):
        body = "function processEvent(event)\n  return event\nend"
        assert "function process(event, emit)" not in body

    def test_wrapped_body_contains_both(self):
        body = "function processEvent(event)\n  return event\nend"
        wrapped = wrap_for_observo(body)
        assert "function processEvent" in wrapped
        assert "function process(event, emit)" in wrapped
