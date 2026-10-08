from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from constants import AGENT_MODEL
from models.validation_models import ValidationReport

try:
    from google.adk.agents import LlmAgent
except ImportError:

    class LlmAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


DOCUMENTATION_INSTRUCTION = """
You are generating migration documentation for one converted operation.

Generate Markdown with: operation heading, summary, conversion notes,
validation results, generated files, and known issues.
Output Markdown only. No JSON.
"""


def generate_operation_doc(
    *,
    operation_id: str,
    channel: str,
    operation_xml: str,
    service_path: str,
    routing_plan_summary: str,
    validation_report: ValidationReport | dict[str, Any],
    shared_components: list[str],
    generated_files: list[str] | None = None,
) -> str:
    """Generate deterministic Markdown documentation for one operation."""
    report = _report_dict(validation_report)
    failure_class = report.get("failure_class")
    known_issues = _known_issues(report)
    files = generated_files or ([service_path] if service_path else [])
    return "\n".join(
        [
            f"## Operation: {operation_id}",
            "",
            f"### Summary",
            f"{operation_id} was migrated for channel {channel}.",
            "",
            "### Conversion notes",
            f"- Routing: {routing_plan_summary or 'No routing summary provided.'}",
            f"- Shared components: {', '.join(shared_components) if shared_components else 'None'}",
            f"- Source XML length: {len(operation_xml)} characters",
            "",
            "### Validation results",
            f"- Build passed: {report.get('build_passed')}",
            f"- Tests passed: {report.get('test_passed')}",
            f"- XML compatibility passed: {report.get('xml_compat_passed')}",
            f"- IBM guard passed: {report.get('ibm_guard_passed')}",
            f"- Behavioral equivalence passed: {report.get('behavior_equiv_passed')}",
            f"- Failure class: {failure_class or 'none'}",
            "",
            "### Files generated",
            *[f"- {path}" for path in files],
            "",
            "### Known issues",
            *(known_issues or ["- None"]),
            "",
        ]
    )


def generate_final_report(conn: sqlite3.Connection, run_id: str, output_path: str) -> None:
    """Write a final Markdown migration report for a run."""
    artifacts = _generated_artifacts(conn, run_id)
    trace_rows = _trace_rows(conn, run_id)
    components = _shared_components(conn, run_id)
    operations = sorted({row["operation_id"] for row in artifacts})
    validated = [row for row in artifacts if row["status"] == "validated"]
    blocked = [row for row in artifacts if row["status"] == "blocked"]
    routing_mismatches = sorted({row["operation_id"] for row in trace_rows if row["failure_class"] == "routing_mismatch"})
    blocked_lines = [f"- {row['operation_id']}: {row['blocking_reason'] or 'unknown'}" for row in blocked] or ["- None"]
    component_lines = [f"- {component}" for component in components] or ["- None"]
    routing_lines = [f"- {operation_id}" for operation_id in routing_mismatches] or ["- None"]
    human_review_lines = [
        f"- {row['operation_id']}: {row['blocking_reason']}"
        for row in blocked
        if row["blocking_reason"] == "needs_human_review"
    ] or ["- None"]
    generated_file_lines = [f"- {row['generated_path']}" for row in artifacts if row["generated_path"]] or ["- None"]
    lines = [
        "# Final Migration Report",
        "",
        "## Executive Summary",
        f"- Run ID: {run_id}",
        f"- Operations migrated: {len(operations)}",
        f"- Operations validated: {len({row['operation_id'] for row in validated})}",
        f"- Blocked operations: {len(blocked)}",
        "",
        "## Operations Migrated",
        *[f"- {operation_id}" for operation_id in operations],
        "",
        "## Blocked Operations",
        *blocked_lines,
        "",
        "## Shared Components Promoted To Common Lib",
        *component_lines,
        "",
        "## Validation Pass Rates",
        f"- Validated artifacts: {len(validated)}/{len(artifacts)}",
        "",
        "## Routing Mismatches Found And Resolved",
        *routing_lines,
        "",
        "## Human Review Items",
        *human_review_lines,
        "",
        "## Files Generated",
        *generated_file_lines,
        "",
    ]
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


def build_human_gate4_report(conn: sqlite3.Connection, run_id: str, output_path: str) -> str:
    """Build the final Human Gate 4 approval prompt."""
    artifacts = _generated_artifacts(conn, run_id)
    total_operations = len({row["operation_id"] for row in artifacts})
    validated = len({row["operation_id"] for row in artifacts if row["status"] == "validated"})
    blocked_human = len({row["operation_id"] for row in artifacts if row["blocking_reason"] == "needs_human_review"})
    shared_components = len(_shared_components(conn, run_id))
    routing_mismatches = len({row["operation_id"] for row in _trace_rows(conn, run_id) if row["failure_class"] == "routing_mismatch"})
    return "\n".join(
        [
            "=== Human Gate 4 ===",
            "Migration complete.",
            "",
            f"Operations validated: {validated}/{total_operations}",
            f"Blocked (needs human review): {blocked_human}",
            f"Shared components in common-lib: {shared_components}",
            f"Routing mismatches detected and fixed: {routing_mismatches}",
            "",
            f"Final report: {output_path}",
            "",
            "Approve for production? (yes/no)",
        ]
    )


def _report_dict(report: ValidationReport | dict[str, Any]) -> dict[str, Any]:
    return report.model_dump(mode="json") if isinstance(report, ValidationReport) else report


def _known_issues(report: dict[str, Any]) -> list[str]:
    issues = []
    failure_class = report.get("failure_class")
    if failure_class:
        issues.append(f"- Failure class: {failure_class}")
    for diff in report.get("xml_diffs") or []:
        for item in diff.get("diffs", []):
            issues.append(f"- XML diff: {item}")
    return issues


def _generated_artifacts(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT operation_id, channel, artifact_kind, generated_path, status, blocking_reason
        FROM generated_artifacts
        WHERE run_id = ?
        ORDER BY operation_id, artifact_kind
        """,
        (run_id,),
    ).fetchall()


def _trace_rows(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT operation_id, failure_class
        FROM trace_comparisons
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchall()


def _shared_components(conn: sqlite3.Connection, run_id: str) -> list[str]:
    return [
        row["component_id"]
        for row in conn.execute(
            """
            SELECT component_id
            FROM component_registry
            WHERE run_id = ? AND used_by_validated_operations > 0
            ORDER BY component_id
            """,
            (run_id,),
        ).fetchall()
    ]


documentation_report_agent = LlmAgent(
    name="DocumentationReportAgent",
    description="Generates per-operation and final migration documentation.",
    model=AGENT_MODEL,
    instruction=DOCUMENTATION_INSTRUCTION,
    tools=[generate_operation_doc, generate_final_report, build_human_gate4_report],
)
