"""Phase 2.C tests: OCSF schema registry keeps 2001/2004/6001 and rejects class_uid=0."""
import pytest


class TestOcsfSchemaRegistryClasses:
    def test_class_2001_present(self):
        from components.testing_harness.ocsf_schema_registry import OCSFSchemaRegistry
        registry = OCSFSchemaRegistry()
        assert registry.has_class(2001), "Class 2001 (Security Finding) must be in the registry"

    def test_class_2004_present(self):
        from components.testing_harness.ocsf_schema_registry import OCSFSchemaRegistry
        registry = OCSFSchemaRegistry()
        assert registry.has_class(2004), "Class 2004 (Detection Finding) must be in the registry"

    def test_class_6001_present(self):
        from components.testing_harness.ocsf_schema_registry import OCSFSchemaRegistry
        registry = OCSFSchemaRegistry()
        assert registry.has_class(6001), "Class 6001 (Application Lifecycle or Activity) must be in the registry"

    @pytest.mark.parametrize("class_uid", [2001, 2004, 6001])
    def test_required_fields_for_class(self, class_uid):
        from components.testing_harness.ocsf_schema_registry import OCSFSchemaRegistry
        registry = OCSFSchemaRegistry()
        fields = registry.required_fields(class_uid)
        expected = {"class_uid", "category_uid", "activity_id", "time", "type_uid", "severity_id"}
        missing = expected - set(fields)
        assert not missing, f"Class {class_uid} missing required fields: {missing}"


class TestClassUidZeroHardReject:
    @pytest.mark.parametrize("bad_assignment", [
        "event.class_uid = 0",
        "event.class_uid=0",
        "event.class_uid =  0",
        "event['class_uid'] = 0",  # subscript form — SHOULD also be caught if the check is complete
    ])
    def test_lint_rejects_class_uid_zero(self, bad_assignment):
        from components.testing_harness.lua_linter import lint_script
        src = f"function processEvent(event) {bad_assignment}; return event end"
        result = lint_script(src, context="lv3")
        assert result.has_hard_reject, f"class_uid = 0 must be hard-rejected: {bad_assignment!r}"

    def test_lint_allows_class_uid_2001(self):
        from components.testing_harness.lua_linter import lint_script
        src = "function processEvent(event) event.class_uid = 2001; return event end"
        result = lint_script(src, context="lv3")
        rule_names = [f.get("rule") or f.get("reason", "") or f.get("description", "") for f in result.hard_reject_findings]
        assert not any("class_uid" in r and "0" in r for r in rule_names), \
            "class_uid = 2001 must NOT trigger the class_uid=0 rule"

    def test_lint_allows_activity_id_zero(self):
        """activity_id = 0 (Unknown) is VALID — only class_uid = 0 is the latent bug."""
        from components.testing_harness.lua_linter import lint_script
        src = "function processEvent(event) event.class_uid = 2004; event.activity_id = 0; return event end"
        result = lint_script(src, context="lv3")
        rule_names = [f.get("rule") or f.get("reason", "") or f.get("description", "") for f in result.hard_reject_findings]
        assert not any("class_uid" in r and "0" in r for r in rule_names), \
            "activity_id = 0 must not trip the class_uid = 0 rule"

    def test_lint_ignores_class_uid_zero_in_comment(self):
        """A comment that mentions the invalid value must not trip the lint."""
        from components.testing_harness.lua_linter import lint_script
        src = """function processEvent(event)
            -- note: class_uid = 0 is an invalid fallback we must avoid
            event.class_uid = 2001
            return event
        end"""
        result = lint_script(src, context="lv3")
        rule_names = [f.get("rule") or f.get("reason", "") or f.get("description", "") for f in result.hard_reject_findings]
        assert not any("class_uid" in r and "0" in r for r in rule_names)
