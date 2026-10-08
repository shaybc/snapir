"""Ensure mapped formatter dependencies are checked before conversion scheduling."""

from types import SimpleNamespace

import pytest

from tests.test_closure_builder import add_ready_fixture, RUN_ID
from tools.conversion_tools.closure_builder_tool import build_operation_closure
from tools.conversion_tools.conversion_component_set import checked_conversion_units


def closure(conn, root, vault):
    return build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(root), str(vault),
                                   classpath_index=SimpleNamespace(classes={}, issues=[]))


def test_formatter_missing_superclass_blocks_readiness(tmp_path):
    conn, root, vault = add_ready_fixture(tmp_path)
    (root / "com/bank/CCString.java").write_text("package com.bank; public class CCString extends MissingBase {}")
    result = closure(conn, root, vault)
    assert result.status.value != "READY"
    finding = next(issue for issue in result.blocking_issues if issue.entity_id == "MissingBase")
    assert "Mapped tag CCString" in finding.detail
    assert "com.bank.CCString" in finding.detail


def test_same_package_dependency_is_checked_and_scheduled(tmp_path):
    conn, root, vault = add_ready_fixture(tmp_path)
    (root / "com/bank/CCString.java").write_text("package com.bank; public class CCString extends Base {}")
    (root / "com/bank/Base.java").write_text("package com.bank; public class Base {}")
    result = closure(conn, root, vault)
    assert result.status.value == "READY"
    units, _ = checked_conversion_units(result.model_dump(mode="json"))
    assert {unit[1] for unit in units if unit[0] == "ibm_java"} == {"com.bank.ops.StepA", "com.bank.CCString", "com.bank.Base"}
    (root / "com/bank/Base.java").write_text("package com.bank; public class Base { int changed; }")
    with pytest.raises(ValueError, match="changed after dependency checking"):
        checked_conversion_units(result.model_dump(mode="json"))


def test_scheduler_refuses_unchecked_ready_closure():
    with pytest.raises(ValueError, match="refreshed"):
        checked_conversion_units({"status": "READY"})


def test_formatter_missing_interface_blocks_readiness(tmp_path):
    conn, root, vault = add_ready_fixture(tmp_path)
    (root / "com/bank/CCString.java").write_text("package com.bank; public class CCString implements MissingContract {}")
    result = closure(conn, root, vault)
    assert result.status.value != "READY"
    assert any(issue.entity_id == "MissingContract" for issue in result.blocking_issues)


def test_framework_superclass_without_source_is_replacement(tmp_path):
    conn, root, vault = add_ready_fixture(tmp_path)
    (root / "com/bank/CCString.java").write_text("package com.bank; import com.ibm.dse.base.Element; public class CCString extends Element {}")
    result = closure(conn, root, vault)
    assert result.status.value == "READY"
    assert any(item["class_name"] == "com.ibm.dse.base.Element" for item in result.external_dependencies)


def test_framework_package_source_is_still_scheduled(tmp_path):
    conn, root, vault = add_ready_fixture(tmp_path)
    (root / "com/bank/CCString.java").write_text("package com.bank; import com.ibm.dse.base.Element; public class CCString extends Element {}")
    source = root / "com/ibm/dse/base/Element.java"
    source.parent.mkdir(parents=True)
    source.write_text("package com.ibm.dse.base; public class Element {}")
    result = closure(conn, root, vault)
    assert result.status.value == "READY"
    assert any(item.logical_id == "com.ibm.dse.base.Element" for item in result.conversion_components)
    assert not result.external_dependencies


def test_jdk_type_in_framework_package_is_not_replacement(tmp_path):
    conn, root, vault = add_ready_fixture(tmp_path)
    source = root / "com/ibm/dse/base/Element.java"
    source.parent.mkdir(parents=True)
    source.write_text("package com.ibm.dse.base; public class Element { String value; }")
    (root / "com/bank/CCString.java").write_text("package com.bank; import com.ibm.dse.base.Element; public class CCString extends Element {}")
    result = build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(root), str(vault),
        classpath_index=SimpleNamespace(classes={"java.lang.String": ["jdk"]}, issues=[]))
    assert result.status.value == "READY"
    assert not result.external_dependencies
