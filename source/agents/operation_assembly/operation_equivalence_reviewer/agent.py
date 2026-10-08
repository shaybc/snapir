from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Callable

from constants import AGENT_MODEL, FORBIDDEN_DEPENDENCIES
from models.conversion_models import (
    ContextPlan,
    EquivalenceReviewResult,
    RoutingPlan,
    SerializationPlan,
)
from tools.state_store_tools._json import dumps, utc_now
from tools.state_store_tools.agent_tasks import get_agent_task
from tools.state_store_tools.context_plans import get_context_plan
from tools.state_store_tools.routing_plans import get_routing_plan
from tools.state_store_tools.serialization_plans import get_serialization_plan

try:
    from google.adk.agents import LlmAgent
except ImportError:

    class LlmAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


EQUIVALENCE_REVIEW_INSTRUCTION = """
You are reviewing a generated Java service class for correctness.

You have four inputs to check against. Verify each checklist item.

OPERATION_ID: {operation_id}
CHANNEL: {channel}
ORIGINAL_WSBCC_XML: {operation_xml}
ROUTING_PLAN: {routing_plan_json}
CONTEXT_PLAN: {context_plan_json}
SERIALIZATION_PLAN: {serialization_plan_json}
GENERATED_SERVICE_CLASS: {java_source}

CHECKLIST (verify every item):
1. Every step_id in routing_plan.steps appears in the execute() method.
2. Every RC transition in routing_plan has a corresponding if/else/switch branch.
3. Every on{N}Return in routing_plan appears as an error reply switch.
4. Every field in context_plan.init_sequence appears in initializeContext().
5. Every ParseStep in serialization_plan.request_parsing appears in deserializeRequest().
6. Every DbLookupRequirement in serialization_plan.db_lookups appears in enrichWithDbLookups().
7. No IBM imports remain.
8. No logic appears in DTO classes.
9. The execute() method creates a new context instance per call.
10. Return types match the plan.

Output ONLY JSON. No explanation.
"""


RevisionRunner = Callable[[sqlite3.Connection, str, list[str]], None]
ReviewRunner = Callable[[str, RoutingPlan, ContextPlan, SerializationPlan], EquivalenceReviewResult]


def review_operation_equivalence(
    java_source: str,
    routing_plan: RoutingPlan,
    context_plan: ContextPlan,
    serialization_plan: SerializationPlan,
    forbidden: list[str] | None = None,
    *,
    expected_return_type: str | None = None,
) -> EquivalenceReviewResult:
    """Review a generated service class against deterministic assembly plans."""
    execute_body = _method_body(java_source, "execute") or ""
    initialize_body = _method_body(java_source, "initializeContext") or ""
    request_body = _method_body(java_source, "deserializeRequest") or ""
    lookup_body = _method_body(java_source, "enrichWithDbLookups") or ""
    error_body = _method_body(java_source, "serializeErrorReply") or ""

    missing_steps = _missing_steps(execute_body, routing_plan)
    missing_rc_branches = _missing_rc_branches(execute_body, routing_plan)
    context_issues = _context_issues(java_source, execute_body, initialize_body, context_plan)
    logic_differences = _logic_differences(
        java_source,
        execute_body,
        error_body,
        request_body,
        lookup_body,
        routing_plan,
        context_plan,
        serialization_plan,
        forbidden or FORBIDDEN_DEPENDENCIES,
        expected_return_type,
    )
    issues = missing_steps + missing_rc_branches + context_issues + logic_differences
    return EquivalenceReviewResult(
        operation_id=routing_plan.operation_id,
        missing_steps=missing_steps,
        missing_rc_branches=missing_rc_branches,
        context_mutation_issues=context_issues,
        logic_differences=logic_differences,
        confidence="high" if not issues else "medium",
        review_status="approved" if not issues else "needs_revision",
    )


def run_operation_equivalence_reviewer(
    conn: sqlite3.Connection,
    task_id: str,
    operation_id: str,
    channel: str,
    run_id: str,
    service_path: str,
    *,
    reviewer: ReviewRunner | None = None,
    revision_runner: RevisionRunner | None = None,
    max_revision_cycles: int = 2,
) -> EquivalenceReviewResult:
    """Review assembled operation service and update task/artifact state."""
    routing_plan, context_plan, serialization_plan = _load_plans(conn, operation_id, channel, run_id)
    path = Path(service_path)
    review = reviewer or review_operation_equivalence
    task = get_agent_task(conn, task_id)

    for cycle in range(max_revision_cycles + 1):
        java_source = path.read_text(encoding="utf-8")
        result = review(java_source, routing_plan, context_plan, serialization_plan)
        if result.review_status == "approved":
            _mark_assembly_complete(conn, task_id, operation_id, run_id, result)
            return result
        if result.review_status == "needs_human_review" or cycle >= max_revision_cycles:
            escalated = result
            if result.review_status != "needs_human_review":
                escalated = result.model_copy(update={"review_status": "needs_human_review", "confidence": "low"})
            _mark_needs_human_review(conn, task_id, operation_id, run_id, escalated)
            return escalated
        _mark_revision_pending(conn, task_id, cycle + 1, result)
        if revision_runner:
            revision_runner(conn, task_id, _all_issue_notes(result))
        task = get_agent_task(conn, task_id) or task
    raise RuntimeError("unreachable review loop exit")


def build_human_gate3_report(review_results: list[EquivalenceReviewResult], sample_paths: list[str]) -> str:
    """Build the Human Gate 3 pilot assembly summary."""
    approved = sum(1 for result in review_results if result.review_status == "approved")
    needs_revision = sum(1 for result in review_results if result.review_status == "needs_revision")
    needs_human_review = sum(1 for result in review_results if result.review_status == "needs_human_review")
    return "\n".join(
        [
            "=== Human Gate 3 ===",
            f"Operations assembled: {len(review_results)}",
            f"Approved: {approved}",
            f"Needs revision (pending retry): {needs_revision}",
            f"Needs human review: {needs_human_review}",
            "",
            f"Sample assembled services: {sample_paths}",
            "Review and approve pilot batch? (yes/no)",
        ]
    )


def _missing_steps(execute_body: str, routing_plan: RoutingPlan) -> list[str]:
    missing = []
    for step in routing_plan.steps:
        simple_impl = step.impl_class.rsplit(".", 1)[-1]
        accepted_markers = {step.step_id, simple_impl, _lower_first(simple_impl)}
        if not any(marker and marker in execute_body for marker in accepted_markers):
            missing.append(step.step_id)
    return missing


def _missing_rc_branches(execute_body: str, routing_plan: RoutingPlan) -> list[str]:
    missing = []
    for step in routing_plan.steps:
        for rc in step.transitions:
            if rc == "other":
                if "else" not in execute_body and "default:" not in execute_body:
                    missing.append(f"{step.step_id}:RC {rc}")
                continue
            if not _contains_rc_branch(execute_body, str(rc)):
                missing.append(f"{step.step_id}:RC {rc}")
    return missing


def _context_issues(
    java_source: str,
    execute_body: str,
    initialize_body: str,
    context_plan: ContextPlan,
) -> list[str]:
    issues = []
    for entry in context_plan.init_sequence:
        if entry.field_name not in initialize_body:
            issues.append(f"missing context initialization: {entry.field_name}")
    if context_plan.context_class:
        field_pattern = rf"private\s+(?:final\s+)?{re.escape(context_plan.context_class)}\s+\w+\s*;"
        new_context_pattern = rf"new\s+{re.escape(context_plan.context_class)}\s*\("
        if re.search(field_pattern, java_source):
            issues.append("context is stored as a service field")
        if not re.search(new_context_pattern, execute_body):
            issues.append("execute does not create a new context instance")
    return issues


def _logic_differences(
    java_source: str,
    execute_body: str,
    error_body: str,
    request_body: str,
    lookup_body: str,
    routing_plan: RoutingPlan,
    context_plan: ContextPlan,
    serialization_plan: SerializationPlan,
    forbidden: list[str],
    expected_return_type: str | None = None,
) -> list[str]:
    issues = []
    for step in routing_plan.steps:
        for return_name in step.return_body_switches:
            if return_name not in execute_body and return_name not in error_body:
                issues.append(f"missing error format: {return_name}")
    for parse_step in serialization_plan.request_parsing:
        if parse_step.field_name not in request_body and parse_step.xml_path not in request_body:
            issues.append(f"missing request parse: {parse_step.field_name}")
    for lookup in serialization_plan.db_lookups:
        if lookup.field_name not in lookup_body and lookup.from_table not in lookup_body:
            issues.append(f"missing db lookup: {lookup.field_name}")
    for pattern in forbidden:
        if pattern in java_source:
            issues.append(f"IBM dependency remains: {pattern}")
    if _dto_class_contains_logic(java_source):
        issues.append("DTO class contains logic")
    expected_return = expected_return_type or f"{routing_plan.operation_id}Response"
    accepted_return = "(?:" + re.escape(expected_return) + "|" + re.escape(expected_return.rsplit(".", 1)[-1]) + ")"
    signature_pattern = rf"public\s+{accepted_return}\s+execute\s*\("
    if not re.search(signature_pattern, java_source):
        issues.append(f"execute return type does not match {expected_return}")
    if context_plan.operation_id != routing_plan.operation_id:
        issues.append("context plan operation does not match routing plan")
    return issues


def _contains_rc_branch(source: str, rc: str) -> bool:
    escaped = re.escape(rc)
    patterns = [
        rf"==\s*{escaped}\b",
        rf"case\s+{escaped}\s*:",
        rf"equals\s*\(\s*\"{escaped}\"\s*\)",
        rf"\"{escaped}\"",
    ]
    return any(re.search(pattern, source) for pattern in patterns)


def _dto_class_contains_logic(java_source: str) -> bool:
    for match in re.finditer(r"class\s+\w*Dto\b|class\s+\w*Request\b|class\s+\w*Response\b", java_source):
        body = _class_body(java_source, match.end())
        if body and re.search(r"\b(if|for|while|switch|try)\b", body):
            return True
    return False


def _class_body(source: str, search_from: int) -> str | None:
    open_brace = source.find("{", search_from)
    if open_brace == -1:
        return None
    close_brace = _matching_brace(source, open_brace)
    if close_brace is None:
        return None
    return source[open_brace + 1 : close_brace]


def _method_body(java_source: str, method_name: str) -> str | None:
    signature = re.search(
        rf"\b(?:public|private|protected)\s+[\w<>\[\], ?]+\s+{re.escape(method_name)}\s*\(",
        java_source,
    )
    if not signature:
        return None
    open_brace = java_source.find("{", signature.end())
    if open_brace == -1:
        return None
    close_brace = _matching_brace(java_source, open_brace)
    if close_brace is None:
        return None
    return java_source[open_brace + 1 : close_brace]


def _matching_brace(source: str, open_brace: int) -> int | None:
    depth = 0
    for index in range(open_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _load_plans(
    conn: sqlite3.Connection,
    operation_id: str,
    channel: str,
    run_id: str,
) -> tuple[RoutingPlan, ContextPlan, SerializationPlan]:
    routing = get_routing_plan(conn, operation_id, channel, run_id)
    context = get_context_plan(conn, operation_id, channel, run_id)
    serialization = get_serialization_plan(conn, operation_id, channel, run_id)
    if not routing or not routing.get("plan_json"):
        raise KeyError("RoutingPlan not found")
    if not context or not context.get("plan_json"):
        raise KeyError("ContextPlan not found")
    if not serialization or not serialization.get("plan_json"):
        raise KeyError("SerializationPlan not found")
    return (
        RoutingPlan(**routing["plan_json"]),
        ContextPlan(**context["plan_json"]),
        SerializationPlan(**serialization["plan_json"]),
    )


def _mark_assembly_complete(
    conn: sqlite3.Connection,
    task_id: str,
    operation_id: str,
    run_id: str,
    result: EquivalenceReviewResult,
) -> None:
    _update_task_review(conn, task_id, "completed", None, result, None)
    _update_operation_artifacts(conn, operation_id, run_id, "assembly_complete", result.review_status, _all_issue_notes(result), None)


def _mark_revision_pending(
    conn: sqlite3.Connection,
    task_id: str,
    attempt_number: int,
    result: EquivalenceReviewResult,
) -> None:
    _update_task_review(conn, task_id, "needs_revision", None, result, attempt_number)


def _mark_needs_human_review(
    conn: sqlite3.Connection,
    task_id: str,
    operation_id: str,
    run_id: str,
    result: EquivalenceReviewResult,
) -> None:
    _update_task_review(conn, task_id, "needs_human_review", "equivalence_gap", result, None)
    _update_operation_artifacts(conn, operation_id, run_id, "needs_human_review", result.review_status, _all_issue_notes(result), "equivalence_gap")


def _update_task_review(
    conn: sqlite3.Connection,
    task_id: str,
    status: str,
    blocking_reason: str | None,
    result: EquivalenceReviewResult,
    attempt_number: int | None,
) -> None:
    assignments = [
        "status = ?",
        "blocking_reason = ?",
        "output_json = ?",
        "updated_at = ?",
    ]
    values: list[object] = [status, blocking_reason, dumps(result.model_dump(mode="json")), utc_now()]
    if attempt_number is not None:
        assignments.append("attempt_number = ?")
        values.append(attempt_number)
    values.append(task_id)
    conn.execute(
        f"""
        UPDATE agent_tasks
        SET {", ".join(assignments)}
        WHERE task_id = ?
        """,
        values,
    )
    conn.commit()


def _update_operation_artifacts(
    conn: sqlite3.Connection,
    operation_id: str,
    run_id: str,
    status: str,
    review_status: str,
    review_notes: list[str],
    blocking_reason: str | None,
) -> None:
    conn.execute(
        """
        UPDATE native_java_artifacts
        SET status = ?,
            review_status = ?,
            review_notes_json = ?,
            blocking_reason = ?,
            updated_at = ?
        WHERE conversion_id = ? AND run_id = ? AND kind = 'xml_operation'
        """,
        (status, review_status, dumps(review_notes), blocking_reason, utc_now(), operation_id, run_id),
    )
    conn.commit()


def _all_issue_notes(result: EquivalenceReviewResult) -> list[str]:
    return [
        *result.missing_steps,
        *result.missing_rc_branches,
        *result.context_mutation_issues,
        *result.logic_differences,
    ]


def _lower_first(value: str) -> str:
    return value[:1].lower() + value[1:]


operation_equivalence_reviewer_agent = LlmAgent(
    name="OperationEquivalenceReviewAgent",
    description="Reviews assembled Java services against routing, context, and serialization plans.",
    model=AGENT_MODEL,
    instruction=EQUIVALENCE_REVIEW_INSTRUCTION,
    tools=[review_operation_equivalence, run_operation_equivalence_reviewer],
)
