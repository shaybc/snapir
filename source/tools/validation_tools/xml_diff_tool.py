from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from models.validation_models import XmlDiffResult


def compare_xml(
    expected_xml: str,
    actual_xml: str,
    ignore_whitespace: bool = True,
    ignore_element_order: bool = False,
) -> XmlDiffResult:
    """Compare XML strings structurally, including text and attribute values."""
    try:
        expected_root = ET.fromstring(expected_xml)
        actual_root = ET.fromstring(actual_xml)
    except ET.ParseError as exc:
        return XmlDiffResult(
            operation_id="",
            scenario="xml_compare",
            passed=False,
            diff_count=1,
            diffs=[f"XML parse error: {exc}"],
        )
    diffs = []
    _compare_elements(
        expected_root,
        actual_root,
        path=f"/{_tag_name(expected_root)}",
        diffs=diffs,
        ignore_whitespace=ignore_whitespace,
        ignore_element_order=ignore_element_order,
    )
    return XmlDiffResult(
        operation_id="",
        scenario="xml_compare",
        passed=not diffs,
        diff_count=len(diffs),
        diffs=diffs,
    )


def generate_diff_report(result: XmlDiffResult) -> str:
    """Build a human-readable XML diff report."""
    if result.passed:
        return "XML diff passed: documents are equivalent."
    lines = [f"XML diff failed: {result.diff_count} difference(s)."]
    lines.extend(f"- {diff}" for diff in result.diffs)
    return "\n".join(lines)


def _compare_elements(
    expected: ET.Element,
    actual: ET.Element,
    *,
    path: str,
    diffs: list[str],
    ignore_whitespace: bool,
    ignore_element_order: bool,
) -> None:
    if _tag_name(expected) != _tag_name(actual):
        diffs.append(f"{path}: expected element {_tag_name(expected)}, got {_tag_name(actual)}")
        return
    if expected.attrib != actual.attrib:
        diffs.append(f"{path}: attributes differ expected={expected.attrib} actual={actual.attrib}")
    expected_text = _normalise_text(expected.text, ignore_whitespace)
    actual_text = _normalise_text(actual.text, ignore_whitespace)
    if expected_text != actual_text:
        diffs.append(f"{path}: text differs expected={expected_text!r} actual={actual_text!r}")
    expected_children = list(expected)
    actual_children = list(actual)
    if ignore_element_order:
        expected_children = sorted(expected_children, key=_element_sort_key)
        actual_children = sorted(actual_children, key=_element_sort_key)
    if len(expected_children) != len(actual_children):
        diffs.append(f"{path}: child count differs expected={len(expected_children)} actual={len(actual_children)}")
    for index, (expected_child, actual_child) in enumerate(zip(expected_children, actual_children), start=1):
        child_path = f"{path}/{_tag_name(expected_child)}[{index}]"
        _compare_elements(
            expected_child,
            actual_child,
            path=child_path,
            diffs=diffs,
            ignore_whitespace=ignore_whitespace,
            ignore_element_order=ignore_element_order,
        )


def _normalise_text(text: str | None, ignore_whitespace: bool) -> str:
    value = text or ""
    if ignore_whitespace:
        return re.sub(r"\s+", " ", value).strip()
    return value


def _element_sort_key(element: ET.Element) -> tuple:
    return (_tag_name(element), sorted(element.attrib.items()), _normalise_text(element.text, True))


def _tag_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]
