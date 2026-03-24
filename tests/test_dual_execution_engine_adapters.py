from components.testing_harness.dual_execution_engine import DualExecutionEngine


class _FakeLua:
    def __init__(self, globals_obj):
        self._globals = globals_obj

    def globals(self):
        return self._globals

    def table_from(self, data):
        return dict(data)


def test_invoke_signature_adapter_routes_to_canonical_process_event(monkeypatch):
    engine = DualExecutionEngine()

    monkeypatch.setattr(engine, "_execute_process_event", lambda lua, event: ({"ok": True}, None))
    monkeypatch.setattr(engine, "_execute_transform_compat", lambda lua, event: ({"legacy": True}, None))
    monkeypatch.setattr(engine, "_execute_process_compat", lambda lua, event: ({"emit": True}, None))

    out, err = engine._invoke_signature_adapter(_FakeLua(object()), "processEvent", {"v": 1})

    assert err is None
    assert out == {"ok": True}


def test_process_event_adapter_extracts_embedded_log_payload():
    engine = DualExecutionEngine()

    class _Globals:
        @staticmethod
        def processEvent(event):
            return {
                "1": "drop-me",
                "log": {
                    "class_uid": 3002,
                    "category_uid": 3,
                    "activity_id": 1,
                    "message": "ok",
                },
            }

    out, err = engine._execute_process_event(_FakeLua(_Globals()), {"src": "value"})

    assert err is None
    assert out == {
        "class_uid": 3002,
        "category_uid": 3,
        "activity_id": 1,
        "message": "ok",
    }


def test_transform_and_process_compatibility_adapters_remain_supported():
    engine = DualExecutionEngine()

    class _Globals:
        @staticmethod
        def transform(record):
            out = dict(record)
            out["path"] = "transform"
            return out

        @staticmethod
        def process(event, emit):
            out = {"log": {"class_uid": 1, "activity_id": 2, "category_uid": 3, "path": "process"}}
            emit(out)

    lua = _FakeLua(_Globals())

    transform_out, transform_err = engine._execute_transform_compat(lua, {"value": 5})
    process_out, process_err = engine._execute_process_compat(lua, {"value": 5})

    assert transform_err is None
    assert transform_out["path"] == "transform"

    assert process_err is None
    assert process_out["path"] == "process"
    assert process_out["class_uid"] == 1
