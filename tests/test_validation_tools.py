from __future__ import annotations

from tools.validation_tools.ibm_dependency_guard_tool import (
    is_clean,
    scan_for_ibm_dependencies,
    scan_source,
)
from tools.validation_tools.xml_diff_tool import compare_xml, generate_diff_report


def test_ibm_guard_finds_forbidden_import(tmp_path):
    java_file = tmp_path / "Legacy.java"
    java_file.write_text("import com.ibm.dse.base.CCOperationStep;\npublic class Legacy {}\n", encoding="utf-8")

    findings = scan_for_ibm_dependencies(str(tmp_path), ["com.ibm"])

    assert len(findings) == 1
    assert "Legacy.java:1:com.ibm" in findings[0]


def test_ibm_guard_clean_spring_service_returns_empty(tmp_path):
    java_file = tmp_path / "Service.java"
    java_file.write_text("import org.springframework.stereotype.Service;\n@Service public class Service {}\n", encoding="utf-8")

    assert scan_for_ibm_dependencies(str(tmp_path), ["com.ibm", "websphere"]) == []
    assert is_clean(str(tmp_path), ["com.ibm", "websphere"]) is True


def test_ibm_guard_catches_class_for_name_string_literal():
    source = 'public class Loader { void load() throws Exception { Class.forName("com.ibm.Legacy"); } }'

    assert scan_source(source, ["com.ibm"]) == ["com.ibm"]


def test_xml_diff_identical_xml_passes():
    result = compare_xml("<root><id>1</id></root>", "<root><id>1</id></root>")

    assert result.passed is True
    assert result.diff_count == 0


def test_xml_diff_different_element_value_fails_with_one_diff():
    result = compare_xml("<root><id>1</id></root>", "<root><id>2</id></root>")

    assert result.passed is False
    assert result.diff_count == 1
    assert "text differs" in result.diffs[0]


def test_xml_diff_extra_actual_element_fails():
    result = compare_xml("<root><id>1</id></root>", "<root><id>1</id><extra>x</extra></root>")

    assert result.passed is False
    assert result.diff_count == 1
    assert "child count differs" in result.diffs[0]


def test_xml_diff_ignores_whitespace_by_default():
    result = compare_xml("<root><name>Jane   Doe</name></root>", "<root>\n  <name>Jane Doe</name>\n</root>")

    assert result.passed is True


def test_generate_diff_report_summarises_failures():
    result = compare_xml("<root><id>1</id></root>", "<root><id>2</id></root>")

    assert "XML diff failed: 1 difference(s)." in generate_diff_report(result)
