from components.testing_harness.dual_execution_engine import DualExecutionEngine


def test_execute_orders_events_deterministically(monkeypatch):
    from components.testing_harness import dual_execution_engine as engine_module

    engine = DualExecutionEngine()

    calls = []

    def fake_execute_single(lua_code, signature, event_data, test_name, ocsf_required):
        calls.append(test_name)
        return {
            "test_name": test_name,
            "status": "passed",
            "input_event": event_data,
            "output_event": event_data,
            "error": None,
            "execution_time_ms": 0.0,
            "field_trace": [],
            "ocsf_validation": {
                "required_present": [],
                "required_missing": [],
                "coverage_pct": 100,
            },
        }

    monkeypatch.setattr(engine_module, "LUPA_AVAILABLE", True)
    monkeypatch.setattr(engine, "_execute_single", fake_execute_single)

    events = [
        {"name": "zeta", "event": {"b": 2}},
        {"name": "alpha", "event": {"a": 1}},
        {"name": "beta", "event": {"a": 1, "b": 2}},
    ]

    first = engine.execute("function processEvent(event) return event end", events)
    second = engine.execute("function processEvent(event) return event end", list(reversed(events)))

    assert [r["test_name"] for r in first["results"]] == ["alpha", "beta", "zeta"]
    assert [r["test_name"] for r in second["results"]] == ["alpha", "beta", "zeta"]
    assert calls[:3] == ["alpha", "beta", "zeta"]


def test_field_trace_order_is_stable_with_unordered_dict_inputs():
    engine = DualExecutionEngine()

    input_event = {"z": 3, "a": 1, "m": 2}
    output_event = {"mapped_z": 3, "mapped_a": 1}

    trace_a = engine._build_field_trace(input_event, output_event)
    trace_b = engine._build_field_trace(dict(reversed(list(input_event.items()))), output_event)

    assert trace_a == trace_b
    assert [item["output_field"] for item in trace_a[:2]] == ["mapped_a", "mapped_z"]


def test_flatten_returns_deterministic_key_order():
    engine = DualExecutionEngine()

    payload = {
        "z": {"k2": 2, "k1": 1},
        "a": 0,
    }

    flat = engine._flatten(payload, "")

    assert list(flat.keys()) == ["a", "z.k1", "z.k2"]
