"""Verify batch dependency totals count shared definitions once."""

from types import SimpleNamespace

from agents.migration_planning.batch_composition import composition_lines


def test_shared_formats_are_deduplicated_across_operations():
    packets = [SimpleNamespace(channel="INTERNET", operation_id=name) for name in ("A", "B")]
    inventory = {
        ("INTERNET", "A"): {"format": {"shared": "SharedFormat", "a": "RequestA"},
                            "decorator": {"padding": "Padding"}},
        ("INTERNET", "B"): {"format": {"shared": "SharedFormat", "b": "RequestB"}},
        ("IVR", "C"): {"format": {"other": "OutsideScope"}},
    }
    report = "\n".join(composition_lines(packets, inventory))
    assert "Format definitions | 3" in report
    assert "Decorator definitions | 1" in report
    assert "Format definitions: 2" in report
    assert "SharedFormat" in report and "RequestA" in report
    assert "OutsideScope" not in report


def test_absent_inventory_is_reported_as_unavailable():
    report = "\n".join(composition_lines([], None))
    assert "inventory unavailable" in report


def test_markdown_component_groups_are_collapsed_with_visible_counts():
    packets = [SimpleNamespace(channel="INTERNET", operation_id="A")]
    inventory = {("INTERNET", "A"): {"format": {"one": "Request <data>"}}}
    report = "\n".join(composition_lines(packets, inventory, collapsible=True))
    assert "Format definitions | 1" in report
    assert "<summary>Format definitions: 1</summary>" in report
    assert "Request &lt;data&gt;" in report
    assert "<details open" not in report
