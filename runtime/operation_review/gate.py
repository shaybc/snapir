"""Persist operation reviews, bound reassembly, and authorize Gate 3 progression."""

import hashlib
import json
from pathlib import Path

from agents.operation_assembly.operation_equivalence_reviewer.agent import build_human_gate3_report
from models.conversion_models import EquivalenceReviewResult
from runtime.component_review import run_component_review_gate
from runtime.managed_projects import create_build_context
from runtime.operation_review.evidence import collect_operation_evidence
from runtime.operation_review.reviewer import review_assembled_operation
from runtime.human_gates import evaluate_gate
from tools.state_store_tools._json import utc_now
from tools.state_store_tools.agent_tasks import upsert_agent_task
from tools.state_store_tools.runs import update_run_status


def run_operation_review_gate(conn, config, profile, plan, directory, *, model_reviewer=None,
                              component_gate=None, project_builder=None, assembly_runner=None) -> str:
    """Require accepted operation reviews and current Gate 3 before service generation."""
    component_gate = component_gate or (lambda: run_component_review_gate(conn, config, profile, plan, directory))
    if component_gate() != "assembly_pending":
        return "component_gate_not_accepted"
    if project_builder is None:
        def project_builder(project):
            context = create_build_context(profile, Path(project), Path(project).name)
            return context.verifier.compile_project(project, context.allowed_ibm_artifacts).returncode == 0
    if assembly_runner is None:
        from runtime.operation_assembly import run_operation_assembly
        assembly_runner = lambda: run_operation_assembly(conn, config, profile, plan, directory)
    conn.execute("""CREATE TABLE IF NOT EXISTS operation_review_snapshots (
        run_id TEXT NOT NULL, operation_id TEXT NOT NULL, channel TEXT NOT NULL, fingerprint TEXT NOT NULL,
        result_json TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(run_id,operation_id,channel,fingerprint))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS operation_revision_attempts (
        run_id TEXT NOT NULL, operation_id TEXT NOT NULL, channel TEXT NOT NULL, attempts INTEGER NOT NULL,
        PRIMARY KEY(run_id,operation_id,channel))""")
    conn.commit()
    update_run_status(conn, config.run_id, "in_progress", "operation_review")
    while True:
        evidence = collect_operation_evidence(conn, config, profile, plan)
        reviews = []
        revise = False
        for item in evidence:
            key = (config.run_id, item["operation_id"], item["channel"])
            if item["issues"]:
                result = EquivalenceReviewResult(operation_id=item["operation_id"], logic_differences=item["issues"],
                                                 confidence="low", review_status="needs_human_review")
            else:
                cached = conn.execute("SELECT result_json FROM operation_review_snapshots WHERE run_id=? AND operation_id=? AND channel=? AND fingerprint=?",
                                      (*key, item["fingerprint"])).fetchone()
                try:
                    result = EquivalenceReviewResult.model_validate_json(cached[0]) if cached else review_assembled_operation(item, profile, model_reviewer)
                except Exception as exc:
                    result = EquivalenceReviewResult(operation_id=item["operation_id"], logic_differences=["Operation review failed: " + type(exc).__name__],
                                                     confidence="low", review_status="needs_human_review")
                conn.execute("""INSERT INTO operation_review_snapshots VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id,operation_id,channel,fingerprint) DO UPDATE SET result_json=excluded.result_json,
                    updated_at=excluded.updated_at""", (*key, item["fingerprint"], result.model_dump_json(), utc_now()))
            if result.review_status == "needs_revision":
                row = conn.execute("SELECT attempts FROM operation_revision_attempts WHERE run_id=? AND operation_id=? AND channel=?", key).fetchone()
                attempts = row[0] if row else 0
                if attempts < config.max_agent_task_retries:
                    conn.execute("""INSERT INTO operation_revision_attempts VALUES (?, ?, ?, ?)
                        ON CONFLICT(run_id,operation_id,channel) DO UPDATE SET attempts=excluded.attempts""", (*key, attempts + 1))
                    notes = [*result.missing_steps, *result.missing_rc_branches, *result.context_mutation_issues, *result.logic_differences]
                    conn.execute("UPDATE agent_tasks SET status='needs_rerun', output_json=?, updated_at=? WHERE task_id=? AND run_id=? AND channel=?",
                                 (json.dumps(dict(equivalence_feedback=notes)), utc_now(), item["assembly_task_id"], config.run_id, item["channel"]))
                    conn.execute("DELETE FROM operation_assembly_snapshots WHERE run_id=? AND operation_id=? AND channel=?", key)
                    revise = True
                else:
                    result = result.model_copy(update=dict(confidence="low", review_status="needs_human_review",
                                                          logic_differences=[*result.logic_differences, "Operation revision limit reached"]))
            review_task = "operation-review-" + hashlib.sha256(":".join(key).encode()).hexdigest()
            upsert_agent_task(conn, task_id=review_task, run_id=config.run_id, agent_name="ManagedOperationReview",
                              scope_type="operation", scope_id=item["operation_id"], channel=item["channel"], target_language="java",
                              status="completed" if result.review_status == "approved" else "needs_human_review",
                              input_data=dict(fingerprint=item["fingerprint"]), output_data=result.model_dump(mode="json"),
                              max_retries=config.max_agent_task_retries)
            # Update this channel's assembly-owned artifacts only.
            conn.execute("""UPDATE native_java_artifacts SET review_status=?, review_notes_json=?, updated_at=?
                WHERE run_id=? AND kind='xml_operation' AND artifact_path=?""",
                (result.review_status, json.dumps([*result.missing_steps, *result.missing_rc_branches,
                  *result.context_mutation_issues, *result.logic_differences]), utc_now(), config.run_id, item["service_path"]))
            reviews.append(result)
        conn.commit()
        if revise:
            update_run_status(conn, config.run_id, "in_progress", "operation_revision")
            try:
                outcome = assembly_runner()
            except Exception:
                outcome = "assembly_blocked"
            if outcome == "operation_review_pending":
                continue
            if outcome == "component_gate_not_accepted":
                return outcome
            break
        break
    builds = {}
    for item in evidence:
        if not item["issues"]:
            try:
                builds[item["project"]] = bool(project_builder(item["project"]))
            except Exception:
                builds[item["project"]] = False
    fresh = collect_operation_evidence(conn, config, profile, plan)
    unchanged = [(item["operation_id"], item["channel"], item["fingerprint"]) for item in fresh] == [
                 (item["operation_id"], item["channel"], item["fingerprint"]) for item in evidence]
    passed = (bool(evidence) and unchanged and all(not item["issues"] for item in fresh) and all(builds.values()) and
              all(result.review_status == "approved" and result.confidence != "low" for result in reviews) and len(reviews) == len(evidence))
    report = build_human_gate3_report(reviews, [item["service_path"] for item in evidence if item["service_path"]])
    report += "\nStatic/model operation review; this is not runtime legacy-response equivalence proof.\n"
    report += json.dumps(dict(operations=[dict(operation_id=item["operation_id"], channel=item["channel"], fingerprint=item["fingerprint"],
                                  blockers=item["issues"]) for item in evidence], reviews=[review.model_dump(mode="json") for review in reviews],
                                  builds=builds, evidence_unchanged=unchanged), sort_keys=True, indent=2)
    (Path(directory) / "gate_3_report.txt").write_text(report, encoding="utf-8")
    decision = evaluate_gate(conn, config.run_id, 3, report, profile.gate_policies.get("3", "human"), passed)
    phase = "service_generation_pending" if decision == "approved" else "operation_review_blocked" if decision == "blocked" else f"gate_3_{decision}"
    update_run_status(conn, config.run_id, "stopped" if decision == "rejected" else "blocked" if decision == "blocked" else "paused", phase)
    return phase
