from __future__ import annotations

import sqlite3
from pathlib import Path

from models.validation_models import TraceComparisonResult
from tools.state_store_tools.trace_comparisons import insert_trace_comparison


def write_comparison_to_db(
    conn: sqlite3.Connection,
    result: TraceComparisonResult,
    operation_id: str,
    channel: str,
    run_id: str,
    scenario: str,
) -> None:
    """Write one trace comparison result to the trace comparison table."""
    insert_trace_comparison(
        conn,
        comparison_id=f"{run_id}:{operation_id}:{scenario}",
        operation_id=operation_id,
        channel=channel,
        run_id=run_id,
        scenario=scenario,
        matched=result.matched,
        step_sequence_match=result.step_sequence_match,
        rc_per_step_match=result.rc_per_step_match,
        context_writes_match=result.context_writes_match,
        reply_format_match=result.reply_format_match,
        final_xml_match=result.final_xml_match,
        failure_class=result.failure_class.value if result.failure_class else None,
        comparison=result.model_dump(mode="json"),
    )


def write_comparison_report(
    result: TraceComparisonResult,
    output_path: str,
) -> None:
    """Write a markdown trace comparison report."""
    lines = [
        "# Trace Comparison",
        "",
        f"- Matched: {result.matched}",
        f"- Step sequence match: {result.step_sequence_match}",
        f"- RC per step match: {result.rc_per_step_match}",
        f"- Context writes match: {result.context_writes_match}",
        f"- Reply format match: {result.reply_format_match}",
        f"- Final XML match: {result.final_xml_match}",
        f"- Failure class: {result.failure_class.value if result.failure_class else 'none'}",
    ]
    if result.step_sequence_diff:
        lines.extend(["", "## Step Sequence Diff", *[f"- {diff}" for diff in result.step_sequence_diff]])
    if result.rc_mismatches:
        lines.extend(["", "## RC Mismatches"])
        lines.extend(f"- {item.step_id}: legacy={item.legacy_rc} generated={item.generated_rc}" for item in result.rc_mismatches)
    if result.context_write_mismatches:
        lines.extend(["", "## Context Write Mismatches"])
        lines.extend(
            f"- {item.step_id}.{item.field_name}: legacy={item.legacy_value} generated={item.generated_value}"
            for item in result.context_write_mismatches
        )
    if result.final_xml_diff:
        lines.extend(["", "## Final XML Diff", *[f"- {diff}" for diff in result.final_xml_diff]])
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_gate_summary(
    conn: sqlite3.Connection,
    run_id: str,
    operation_ids: list[str],
) -> str:
    """Generate a Gate 4 trace-comparison summary for selected operations."""
    placeholders = ",".join("?" for _ in operation_ids)
    rows = conn.execute(
        f"""
        SELECT operation_id, matched, failure_class
        FROM trace_comparisons
        WHERE run_id = ? AND operation_id IN ({placeholders})
        """,
        (run_id, *operation_ids),
    ).fetchall()
    fully_matched = sorted({row["operation_id"] for row in rows if row["matched"]})
    by_failure = {
        "routing_mismatch": sorted({row["operation_id"] for row in rows if row["failure_class"] == "routing_mismatch"}),
        "conversion_gap": sorted({row["operation_id"] for row in rows if row["failure_class"] == "conversion_gap"}),
        "equivalence_gap": sorted({row["operation_id"] for row in rows if row["failure_class"] == "equivalence_gap"}),
    }
    return "\n".join(
        [
            "=== Human Gate 4 ===",
            f"Operations fully matched: {len(fully_matched)}",
            f"Operations with routing_mismatch: {len(by_failure['routing_mismatch'])} {by_failure['routing_mismatch']}",
            f"Operations with conversion_gap: {len(by_failure['conversion_gap'])} {by_failure['conversion_gap']}",
            f"Operations with equivalence_gap: {len(by_failure['equivalence_gap'])} {by_failure['equivalence_gap']}",
        ]
    )
