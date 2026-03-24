from flask import Flask

from components.web_ui import routes as routes_module


class _ServiceStub:
    pending_conversions = {}
    approved_conversions = []
    rejected_conversions = []
    modified_conversions = []

    def get_status(self):
        return {}

    def get_runtime_status(self):
        return {"metrics": {}, "reload_requests": {}, "pending_promotions": {}}

    def request_runtime_reload(self, parser_id):
        return False

    def pop_runtime_reload(self, parser_id):
        return None

    def request_canary_promotion(self, parser_id):
        return False

    def pop_canary_promotion(self, parser_id):
        return None


def test_root_redirects_to_workbench(monkeypatch):
    class FakeWorkbench:
        def _find_entry(self, parser_name):
            return None

        def list_parsers(self):
            return []

        def build_parser(self, parser_name):
            return None

        def build_parser_with_agent(self, parser_name, force_regenerate=False):
            return None

        def _get_agent(self):
            return None

    class FakeHarness:
        pass

    def _no_auth(fn):
        return fn

    monkeypatch.setattr(routes_module, "ParserLuaWorkbench", FakeWorkbench)
    monkeypatch.setattr(routes_module, "HarnessOrchestrator", FakeHarness)

    app = Flask(__name__)
    app.config["TESTING"] = True
    routes_module.register_routes(
        app,
        service=_ServiceStub(),
        feedback_queue=None,
        runtime_service=None,
        event_loop=None,
        require_auth=_no_auth,
        rate_limiter=None,
    )

    resp = app.test_client().get('/', follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/workbench')
