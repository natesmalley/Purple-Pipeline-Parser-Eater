"""Phase 2.A + 2.B tests for components.lua_deploy_wrapper.wrap_for_observo."""
import pytest

from components.lua_deploy_wrapper import wrap_for_observo, ensure_wrapped


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


class TestFindingAIdempotenceFalsePositive:
    """Phase 2.F DA finding A: idempotence must not false-positive on comments/strings."""

    def test_comment_mentioning_wrapper_not_rejected(self):
        """A body that MENTIONS 'function process(event, emit)' in a comment must wrap cleanly."""
        body = (
            "function processEvent(event)\n"
            "    -- note: we define function process(event, emit) at deploy time\n"
            "    return event\n"
            "end"
        )
        wrapped = wrap_for_observo(body)
        assert "function process(event, emit)" in wrapped
        # The comment must be preserved inside the authored body
        assert "we define function process(event, emit) at deploy time" in wrapped

    def test_block_comment_mentioning_wrapper_not_rejected(self):
        body = (
            "function processEvent(event)\n"
            "    --[[ function process(event, emit) is added for us ]]\n"
            "    return event\n"
            "end"
        )
        wrapped = wrap_for_observo(body)
        assert "function process(event, emit)" in wrapped

    def test_string_literal_mentioning_wrapper_not_rejected(self):
        body = (
            "function processEvent(event)\n"
            '    local doc = "see function process(event, emit)"\n'
            "    return event\n"
            "end"
        )
        wrapped = wrap_for_observo(body)
        assert "function process(event, emit)" in wrapped

    def test_sentinel_marker_detected(self):
        """An already-wrapped body (with sentinel) must raise on re-wrap."""
        body = "function processEvent(event) return event end"
        once = wrap_for_observo(body)
        with pytest.raises(ValueError, match="sentinel"):
            wrap_for_observo(once)

    def test_unwrapped_with_real_outer_definition_raises(self):
        """A body that ACTUALLY defines function process(event, emit) outside comments must raise."""
        body = (
            "function processEvent(event) return event end\n"
            "function process(event, emit)\n"
            "    emit(event)\n"
            "end"
        )
        with pytest.raises(ValueError, match="already define"):
            wrap_for_observo(body)


class TestEnsureWrappedIdempotent:
    """Phase 2.F: ensure_wrapped is the non-strict sibling of wrap_for_observo."""

    def test_ensure_wrapped_wraps_plain(self):
        body = "function processEvent(event) return event end"
        result = ensure_wrapped(body)
        assert "function process(event, emit)" in result

    def test_ensure_wrapped_skips_already_wrapped(self):
        body = "function processEvent(event) return event end"
        once = wrap_for_observo(body)
        twice = ensure_wrapped(once)
        assert once == twice, "ensure_wrapped must return identical content when already wrapped"


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
