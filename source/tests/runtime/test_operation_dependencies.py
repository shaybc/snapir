"""Check injected role validation and replay the latest service's missing test seam."""

import json
from pathlib import Path

import pytest

from models.native_unit_bundle import NativeUnitBundle
from models.operation_dependency import OperationDependency
from models.operation_resource import OperationResource
from runtime.behavior_conversion.operation_dependencies import validate_step_injection, constructor_parameters
from runtime.behavior_conversion.operation_resources import required_resources, validate_runtime_resources
from tests.runtime.test_incremental_operation import implementation


def test_injection_requirement_is_scoped_to_assembly_and_not_wording():
    from runtime.behavior_conversion.compatibility import versioned_requirements, compatibility_fingerprint
    from tests.runtime.test_behavior_conversion import profile
    settings = profile()
    unit = {"unit": {"kind": "configured_step"}}
    assert not versioned_requirements(settings, "unit", unit)
    request = {"assembly_phase": "implementation", "required_step_dependencies": [{"binding_id": "step"}]}
    requirements = versioned_requirements(settings, "operation", request)
    assert any(item["requirement_id"] == "operation-step-injection" for item in requirements)
    original = compatibility_fingerprint("operation", request, settings, {}, requirements)
    assert compatibility_fingerprint("operation", dict(request, constructor_example="new explanatory wording"), settings, {}, requirements) == original
    assert compatibility_fingerprint("operation", request, settings, {}, []) != original


def injected():
    bundle = implementation()
    bundle.files[0].content = ("package com.company.generated; import example.Step; public class Flow { "
        "private final Step first; private final Step second; public Flow(Step first, Step second) { "
        "this.first = first; this.second = java.util.Objects.requireNonNull(second); } "
        "public int execute(int input) { int result = this.first.execute(input); return this.second.execute(result); } }")
    bundle.operation_contract.step_dependencies = [OperationDependency(binding_id=binding, unit_id="unit", type_name="example.Step",
        parameter_name=binding, field_name=binding) for binding in ("first", "second")]
    bundle = NativeUnitBundle.model_validate(bundle.model_dump())
    steps = [dict(binding_id=binding, unit_id="unit", allowed_types=["example.Step"]) for binding in ("first", "second")]
    return bundle, steps


def test_two_roles_of_same_type_receive_distinct_supplied_objects():
    bundle, steps = injected()
    validate_step_injection(bundle, steps)
    assert len(constructor_parameters(bundle.files[0].content, "com.company.generated.Flow", ["example.Step"])[0][0]) == 2


@pytest.mark.parametrize("message", ['"second cannot be null"', '() -> "second cannot be null"'])
def test_supplied_step_may_be_checked_with_non_null_message_overloads(message):
    bundle, steps = injected()
    bundle.files[0].content = bundle.files[0].content.replace("requireNonNull(second)", "requireNonNull(second, " + message + ")")
    validate_step_injection(bundle, steps)
    bundle.files[0].content = bundle.files[0].content.replace("requireNonNull(second,", "requireNonNull(first,")
    with pytest.raises(ValueError, match="store supplied second"):
        validate_step_injection(bundle, steps)


@pytest.mark.parametrize("old,new,reason", [
    ("this.first = first;", "this.first = new Step();", "store supplied"),
    ("Step first, Step second", "Step first", "constructor must receive"),
    ("private final Step first", "private final Object first", "field first"),
    ("int result = this.first.execute(input);", "int result = new Step().execute(input);", "not called"),
])
def test_wrong_constructors_are_rejected_with_file_and_reason(old, new, reason):
    bundle, steps = injected()
    bundle.files[0].content = bundle.files[0].content.replace(old, new)
    with pytest.raises(ValueError, match=reason):
        validate_step_injection(bundle, steps)


def test_creation_inside_helper_is_rejected_but_comments_strings_and_test_setup_are_ignored():
    bundle, steps = injected()
    bundle.files[0].content += '// new Step();\n'
    bundle.files[0].content = bundle.files[0].content.replace("int result =", 'String note = "new Step()"; int result =')
    bundle.files.append(bundle.files[0].model_copy(update={"path": "src/test/java/example/Fixture.java", "content": "new example.Step();"}))
    validate_step_injection(bundle, steps)
    bundle.files.append(bundle.files[0].model_copy(update={"path": "src/main/java/example/Hidden.java", "content": "package example; class Hidden { Step make() { return new Step(); } }"}))
    with pytest.raises(ValueError, match="Hidden.java.*do not construct"):
        validate_step_injection(bundle, steps)


def latest():
    return json.loads((Path(__file__).parent / "fixtures/latest_route_connection_failure.json").read_text(encoding="utf-8"))


def test_latest_failure_rejected_before_tests_and_connection_need_discovered(tmp_path):
    saved = latest()
    bundle = NativeUnitBundle.model_validate(saved["implementation"])
    units = saved["accepted_units"]
    steps = [dict(binding_id=binding, unit_id=unit["unit_id"], allowed_types=[api["type_name"] for api in unit["apis"]])
             for binding, unit in units.items() if binding in {"ValidateTransfer", "CheckLimits", "ExecuteTransfer", "FraudCheck"}]
    assert steps
    with pytest.raises(ValueError, match="receive each configured step role"):
        validate_step_injection(bundle, steps)
    for name, content in saved["accepted_sources"].items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    accepted = {unit["unit_id"]: dict(unit, project=str(tmp_path)) for unit in units.values()}
    assert required_resources(steps, accepted) == [dict(input_key="Connection", resource_type="java.sql.Connection", provider_type="javax.sql.DataSource")]


def test_resource_provider_must_be_supplied_acquired_and_released():
    bundle = implementation()
    bundle.operation_contract.runtime_resources = [OperationResource(input_key="Session", resource_type="java.sql.Connection", provider_type="javax.sql.DataSource", parameter_name="database", field_name="database")]
    bundle = NativeUnitBundle.model_validate(bundle.model_dump())
    bundle.files[0].content = ('package com.company.generated; import javax.sql.DataSource; import java.sql.Connection; '
        'public class Flow { private final DataSource database; public Flow(DataSource database) { this.database = database; } '
        'public int execute(int input) throws Exception { try(Connection connection = this.database.getConnection()) { '
        'java.util.Map<String,Object> values = new java.util.HashMap<>(); values.put("Session", connection); return input; } } }')
    required = [dict(input_key="Session", resource_type="java.sql.Connection", provider_type="javax.sql.DataSource")]
    validate_runtime_resources(bundle, required)
    bundle.files[0].content = bundle.files[0].content.replace('values.put("Session", connection);', '')
    with pytest.raises(ValueError, match="input key Session"):
        validate_runtime_resources(bundle, required)
