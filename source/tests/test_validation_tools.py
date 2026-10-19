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


def test_ibm_guard_ignores_line_block_and_javadoc_comments():
    source = '''// import com.ibm.Legacy;
/* Class.forName("com.ibm.Legacy"); */
/**
 * <opStep implClass="com.ibm.il.dse.operations.common.MapErrorByValueAlways" />
 */
public class NativeStep {}'''
    assert scan_source(source, ["com.ibm"]) == []


def test_ibm_guard_preserves_line_numbers_and_checks_code_after_comments(tmp_path):
    source = '''/** implClass="com.ibm.Legacy" */
// com.ibm.Legacy
/* documentation */ import com.ibm.Legacy;
public class Loader { void run() { com.ibm.Legacy.invoke(); } }
'''
    path = tmp_path / 'Loader.java'
    path.write_text(source, encoding='utf-8')
    findings = scan_for_ibm_dependencies(str(path), ['com.ibm'])
    assert findings == [f'{path}:3:com.ibm', f'{path}:4:com.ibm']


def test_ibm_guard_keeps_comment_like_text_inside_runtime_strings():
    source = r'''public class Loader {
 String value = "http://example/*literal*/\"";
 Class<?> type = Class.forName("com.ibm.Legacy");
}'''
    assert scan_source(source, ['com.ibm']) == ['com.ibm']


def test_ibm_guard_keeps_runtime_text_block_content():
    source = '''public class Loader {
 String value = """
 // com.ibm.Legacy
 /* literal text, not a comment */
 """;
}'''
    assert scan_source(source, ['com.ibm']) == ['com.ibm']


def test_comment_masking_preserves_literals_and_offsets():
    from tools.validation_tools.java_comments import mask_java_comments
    source = 'String x = "/* literal */ // literal"; char c = \'/\'; /* hidden */\r\n// hidden\r\n'
    masked = mask_java_comments(source)
    assert '"/* literal */ // literal"' in masked and "char c = '/'" in masked
    assert len(masked) == len(source)
    assert masked.count('\r\n') == source.count('\r\n')
    assert 'hidden' not in masked


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
