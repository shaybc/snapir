"""Check that Gate One presents evidence and ownership without opaque identities."""

import json
import sqlite3
from types import SimpleNamespace

from agents.migration_planning.gate_report import component_and_routing_report
from models.shared_library_plan import SharedLibrary, SharedLibraryPlan


def test_names_routing_and_outside_scope_consumers_are_clear():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE source_artifacts(run_id, kind, logical_id, metadata_json)")
    conn.execute("CREATE TABLE source_implementations(run_id, record_json)")
    conn.execute("CREATE TABLE configured_component_definitions(run_id, record_json)")
    conn.execute("INSERT INTO source_artifacts VALUES(?,?,?,?)", ("run", "opStep", "CheckFunds", json.dumps({
        "parent_operation_id": "Transfer", "source_file": "src/Channel/INTERNET/Transfer.xml",
        "impl_class": "bank.CheckFunds", "transitions": {"onSuccess": "SendFunds", "onOtherDo": "end"}})))
    conn.execute("INSERT INTO source_implementations VALUES(?,?)", ("run", json.dumps({
        "implementation_id": "opaque-hash", "package_name": "bank", "class_name": "CheckFunds", "source_path": "src/bank/CheckFunds.java"})))
    packet = SimpleNamespace(channel="INTERNET", operation_id="Transfer")
    plan = SimpleNamespace(batches=[SimpleNamespace(task_packets=[packet])])
    libraries = SharedLibraryPlan(fingerprint="fingerprint", libraries=[SharedLibrary(
        library_id="shared-opaque", version="version-hash", component_keys=["implementation:opaque-hash"])],
        assignments={"implementation:opaque-hash": "shared-opaque"},
        consumers={"implementation:opaque-hash": ["INTERNET/Transfer", "IVR/Balance"]},
        usage_counts={"implementation:opaque-hash": 5}, library_build_order=["shared-opaque"])
    report = component_and_routing_report(conn, "run", plan, libraries)
    assert "bank.CheckFunds" in report and "src/bank/CheckFunds.java" in report
    assert "Recorded condition onSuccess -> Go to step SendFunds" in report
    assert "Any other result -> Finish the operation" in report
    assert "Selected consumers: INTERNET/Transfer" in report
    assert "Other legacy consumers (outside this migration): IVR/Balance" in report
    assert "Proposed destination: Shared library 1" in report
    assert "implementation:opaque-hash" not in report and "version-hash" not in report
    assert "Shared library 1 (shared-opaque)" in report
    assert "choose Approve a gate" in report
    folded = component_and_routing_report(conn, "run", plan, libraries,
                                         include_ownership=False, collapsible=True)
    assert "<summary>Step: CheckFunds</summary>" in folded
    assert "Implementation: bank.CheckFunds" in folded
    assert "Any other result -&gt; Finish the operation" in folded
    assert "Source: src/Channel/INTERNET/Transfer.xml" in folded
    assert "<details open" not in folded
    ownership = component_and_routing_report(conn, "run", plan, libraries,
                                            include_routing=False, collapsible=True)
    assert "<summary>bank.CheckFunds — shared-opaque</summary>" in ownership
    assert "<li>Proposed destination: Shared library 1 (shared-opaque)</li>" in ownership
    assert "<li>Distinct operation consumers: 5</li>" in ownership
    assert "<li>Selected consumers: INTERNET/Transfer</li>" in ownership
    assert "src/bank/CheckFunds.java" in ownership
    assert "<details open" not in ownership
    conn.close()


def test_missing_evidence_is_explicit():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE source_artifacts(run_id, kind, logical_id, metadata_json)")
    plan = SimpleNamespace(batches=[SimpleNamespace(task_packets=[SimpleNamespace(channel="INTERNET", operation_id="Missing")])])
    report = component_and_routing_report(conn, "run", plan, None)
    assert "No matching step evidence available" in report
    assert "No shared-library inventory is available" in report
    conn.close()
