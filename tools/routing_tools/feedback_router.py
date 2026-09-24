from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from models.common_models import RunConfig
from models.conversion_models import ValidationFailureClass
from models.validation_models import ValidationReport
from tools.state_store_tools._json import loads, utc_now
from tools.state_store_tools.agent_tasks import upsert_agent_task
from tools.state_store_tools.invalidation import HashChange, cascade_invalidation


@dataclass(frozen=True)
class FeedbackAction:
    """A rerun instruction produced from a validation failure."""

    failure_class: ValidationFailureClass
    operation_id: str
    target_agent: str
    affected_artifact_ids: list[str] = field(default_factory=list)
    additional_instructions: str = ""
    retry_count: int = 0


class FeedbackRouter:
    """Route validation failures back to the correct rerun target."""

    def route(
        self,
        conn: sqlite3.Connection,
        report: ValidationReport,
        run_config: RunConfig,
    ) -> FeedbackAction:
        """Return a feedback action for a validation report."""
        failure_class = report.failure_class or ValidationFailureClass.validation_fixture_gap
        if report.attempt_number >= run_config.max_agent_task_retries:
            return FeedbackAction(
                failure_class=failure_class,
                operation_id=report.operation_id,
                target_agent="HumanApprovalAgent",
                affected_artifact_ids=_operation_artifacts(conn, run_config.run_id, report.operation_id),
                additional_instructions="Maximum feedback retries exceeded; preserve last validation evidence.",
                retry_count=report.attempt_number,
            )
        target_agent, instructions = _target_for_failure(failure_class)
        affected = _affected_artifacts(conn, run_config.run_id, report.operation_id, failure_class)
        return FeedbackAction(
            failure_class=failure_class,
            operation_id=report.operation_id,
            target_agent=target_agent,
            affected_artifact_ids=affected,
            additional_instructions=instructions,
            retry_count=report.attempt_number + 1,
        )

    def apply_feedback(
        self,
        conn: sqlite3.Connection,
        action: FeedbackAction,
        run_config: RunConfig,
    ) -> None:
        """Apply a feedback action by marking rerun or human-review state."""
        if action.target_agent == "HumanApprovalAgent":
            _mark_needs_human_review(conn, run_config.run_id, action.operation_id)
            return
        if action.failure_class == ValidationFailureClass.shared_component_gap:
            _cascade_shared_component_feedback(conn, run_config.run_id, action.affected_artifact_ids)
        else:
            _mark_operation_needs_rerun(conn, run_config.run_id, action.operation_id)
        upsert_agent_task(
            conn,
            run_id=run_config.run_id,
            agent_name=action.target_agent,
            scope_type="operation",
            scope_id=action.operation_id,
            channel="feedback",
            target_language="java",
            status="needs_rerun",
            attempt_number=action.retry_count,
            input_data={"additional_instructions": action.additional_instructions},
        )


def _target_for_failure(failure_class: ValidationFailureClass) -> tuple[str, str]:
    targets = {
        ValidationFailureClass.build_failure: (
            "JavaServiceGenerationAgent",
            "Re-run Java service generation after compile failure.",
        ),
        ValidationFailureClass.conversion_gap: (
            "IbmJavaCleanerAgent",
            "Re-run IBM Java conversion, then assembly, generation, and validation.",
        ),
        ValidationFailureClass.equivalence_gap: (
            "JavaServiceGenerationAgent",
            "Re-run service generation with code equivalence review evidence.",
        ),
        ValidationFailureClass.shared_component_gap: (
            "IbmJavaCleanerAgent",
            "Re-run shared component conversion and invalidate dependent operations.",
        ),
        ValidationFailureClass.routing_mismatch: (
            "StepImplementationInserterAgent",
            "Re-run pass 3 for execute() with trace diff evidence.",
        ),
        ValidationFailureClass.validation_fixture_gap: (
            "validation_tools",
            "Regenerate golden XML pairs and stub specs; re-run validation only.",
        ),
    }
    return targets[failure_class]


def _affected_artifacts(
    conn: sqlite3.Connection,
    run_id: str,
    operation_id: str,
    failure_class: ValidationFailureClass,
) -> list[str]:
    if failure_class == ValidationFailureClass.shared_component_gap:
        rows = conn.execute(
            """
            SELECT component_id
            FROM component_registry
            WHERE run_id IN (?, 'global') AND used_by_operations_json LIKE ?
            """,
            (run_id, f'%"{operation_id}"%'),
        ).fetchall()
        return [row["component_id"] for row in rows]
    return _operation_artifacts(conn, run_id, operation_id)


def _operation_artifacts(conn: sqlite3.Connection, run_id: str, operation_id: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT artifact_id
        FROM generated_artifacts
        WHERE run_id = ? AND operation_id = ?
        """,
        (run_id, operation_id),
    ).fetchall()
    return [row["artifact_id"] for row in rows]


def _mark_operation_needs_rerun(conn: sqlite3.Connection, run_id: str, operation_id: str) -> None:
    conn.execute(
        """
        UPDATE generated_artifacts
        SET status = 'needs_rerun', updated_at = ?
        WHERE run_id = ? AND operation_id = ?
        """,
        (utc_now(), run_id, operation_id),
    )
    conn.commit()


def _mark_needs_human_review(conn: sqlite3.Connection, run_id: str, operation_id: str) -> None:
    conn.execute(
        """
        UPDATE generated_artifacts
        SET status = 'needs_human_review',
            blocking_reason = 'max_retries_exceeded',
            updated_at = ?
        WHERE run_id = ? AND operation_id = ?
        """,
        (utc_now(), run_id, operation_id),
    )
    conn.execute(
        """
        UPDATE agent_tasks
        SET status = 'needs_human_review',
            blocking_reason = 'max_retries_exceeded',
            updated_at = ?
        WHERE run_id = ? AND scope_id = ?
        """,
        (utc_now(), run_id, operation_id),
    )
    conn.commit()


def _cascade_shared_component_feedback(
    conn: sqlite3.Connection,
    run_id: str,
    component_ids: list[str],
) -> None:
    changes = []
    for component_id in component_ids:
        row = conn.execute(
            """
            SELECT *
            FROM component_registry
            WHERE component_id = ?
            """,
            (component_id,),
        ).fetchone()
        if row is None:
            continue
        affected = loads(row["used_by_operations_json"], []) or []
        changes.append(
            HashChange(
                artifact_id=row["component_id"],
                artifact_kind=row["artifact_kind"],
                logical_id=row["logical_id"],
                old_hash=row["source_hash"],
                new_hash=f"{row['source_hash']}:feedback",
                shared=True,
                affected_operation_ids=affected,
            )
        )
    if changes:
        cascade_invalidation(conn, run_id, changes)
