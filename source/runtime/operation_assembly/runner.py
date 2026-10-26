"""Run checkpointed assembly only after current component-gate acceptance."""

from runtime.workspace_paths import run_report_path, write_run_report
import hashlib
import json
from pathlib import Path

from agents.operation_assembly.service_skeleton_generator.agent import write_and_compile_service_skeleton
from agents.operation_assembly.step_implementation_inserter.agent import run_step_implementation_inserter
from runtime.component_review import run_component_review_gate
from runtime.component_review.evidence import collect_component_evidence
from runtime.managed_projects import create_build_context
from runtime.operation_assembly.generation import generate_skeleton, make_pass_generator, skeleton_path
from runtime.operation_assembly.plans import prepare_assembly_plans
from tools.state_store_tools._json import utc_now
from tools.state_store_tools.agent_tasks import get_agent_task, upsert_agent_task, update_task_status
from tools.state_store_tools.operation_closures import get_operation_closure
from tools.state_store_tools.runs import update_run_status


def run_operation_assembly(conn, config, profile, plan, directory, *, gate_checker=None,
                           plan_builder=prepare_assembly_plans, context_factory=create_build_context,
                           skeleton_generator=generate_skeleton, pass_factory=make_pass_generator, model_call=None) -> str:
    """Assemble every approved operation; persist blocked outcomes and reusable successes.

    This phase stops before operation equivalence review and Gate 3. No assembly
    completion is inferred from a compiler accepting unimplemented method stubs.
    """
    from tools.conversion_tools.scoped_workflow.preparation import is_scoped_run
    if is_scoped_run(conn, config.run_id):
        from runtime.scoped_native.runner import resume_scoped_pipeline
        resume_scoped_pipeline(conn, config, profile, directory, plan=plan,
                               model_call=model_call, context_factory=context_factory)
        return conn.execute('SELECT current_phase FROM runs WHERE run_id=?', (config.run_id,)).fetchone()[0]
    gate_checker = gate_checker or (lambda: run_component_review_gate(conn, config, profile, plan, directory))
    if gate_checker() != "assembly_pending":
        return "component_gate_not_accepted"
    conn.execute("""CREATE TABLE IF NOT EXISTS operation_assembly_snapshots (
        run_id TEXT NOT NULL, operation_id TEXT NOT NULL, channel TEXT NOT NULL,
        input_hash TEXT NOT NULL, service_path TEXT NOT NULL, service_hash TEXT NOT NULL,
        pom_hash TEXT NOT NULL, PRIMARY KEY(run_id, operation_id, channel))""")
    conn.commit()
    update_run_status(conn, config.run_id, "in_progress", "operation_assembly")
    outcomes = []
    for batch in plan.batches:
        for packet in batch.task_packets:
            identity = f"{config.run_id}:{packet.channel}:{packet.operation_id}"
            task_id = "assembly-" + hashlib.sha256(identity.encode()).hexdigest()
            prior = get_agent_task(conn, task_id)
            attempts = int(prior["attempt_number"]) if prior else 0
            payload = prior.get("input_json") if prior else None
            item = dict(operation_id=packet.operation_id, channel=packet.channel, task_id=task_id)
            try:
                routing, context, serialization = plan_builder(conn, config, packet)
                closure = get_operation_closure(conn, packet.operation_id, packet.channel, config.run_id)
                if closure is None or closure["status"] != "READY":
                    raise ValueError("Operation closure is not READY")
                project = Path(config.output_root) / packet.channel / packet.operation_id
                build_context = context_factory(profile, project, packet.operation_id)
                original_xml = Path(closure["closure_json"].get("source_xml_path", ""))
                if not original_xml.is_absolute():
                    original_xml = Path(config.source_root) / original_xml
                xml = original_xml.read_text(encoding="utf-8")
                evidence = collect_component_evidence(conn, config, profile)
                from runtime.shared_libraries.ownership import task_covers
                supporting = [component for component in evidence if task_covers(component["task_input"], packet.operation_id, packet.channel)]
                if not supporting or any(component["issues"] for component in supporting):
                    raise ValueError("Approved component evidence is missing or stale")
                payload = dict(operation_id=packet.operation_id, channel=packet.channel,
                               service_class=packet.operation_id + "Service", operation_xml=xml,
                               routing_plan=routing.model_dump(mode="json"), context_plan=context.model_dump(mode="json"),
                               serialization_plan=serialization.model_dump(mode="json"),
                               components=[dict(task_id=component["task_id"], kind=component["kind"], logical_id=component["conversion_id"],
                                                java_source=component["converted_source"], fingerprint=component["fingerprint"],
                                                source_component_key=component["task_input"].get("source_component_key"),
                                                library_id=component["task_input"].get("managed_library_id"))
                                           for component in supporting],
                               approved_ibm_classes=profile.allowed_ibm_classes)
                if prior and prior.get("output_json") and prior["output_json"].get("equivalence_feedback"):
                    payload["equivalence_feedback"] = prior["output_json"]["equivalence_feedback"]
                digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                cached = conn.execute("SELECT * FROM operation_assembly_snapshots WHERE run_id=? AND operation_id=? AND channel=?",
                                      (config.run_id, packet.operation_id, packet.channel)).fetchone()
                if cached and cached["input_hash"] == digest and prior and prior["status"] == "completed":
                    path = Path(cached["service_path"])
                    if path.is_file() and _hash(path) == cached["service_hash"] and _hash(Path(build_context.pom_path)) == cached["pom_hash"]:
                        outcomes.append(dict(item, status="assembled", service_path=str(path), reused=True))
                        continue
                if prior and prior["status"] == "blocked" and attempts >= config.max_agent_task_retries:
                    raise ValueError("Assembly retry budget exhausted; operator intervention is required")
                upsert_agent_task(conn, task_id=task_id, run_id=config.run_id, agent_name="ManagedAssembly",
                                  scope_type="operation", scope_id=packet.operation_id, channel=packet.channel,
                                  target_language="java", status="in_progress", attempt_number=attempts,
                                  max_retries=config.max_agent_task_retries, input_data=payload)
                converted = skeleton_generator(profile, payload)
                path = skeleton_path(build_context, packet.operation_id, converted.java_source)
                # Register the assembly-owned path before component coverage is checked again.
                from tools.state_store_tools.native_java_artifacts import upsert_native_java_artifact
                upsert_native_java_artifact(conn, artifact_id=f"{config.run_id}:assembly_output:{task_id}", run_id=config.run_id,
                                            conversion_id=packet.operation_id, kind="xml_operation", logical_id=packet.operation_id,
                                            artifact_path=str(path), status="in_progress")
                status = write_and_compile_service_skeleton(conn, task_id, converted.java_source,
                            packet.operation_id, packet.channel, config.run_id, build_context=build_context,
                            managed_output_path=str(path), dependency_proposals=converted.dependencies)
                if status != "compiled":
                    raise ValueError("Skeleton compilation failed")
                generator = pass_factory(profile, payload, build_context)
                status = run_step_implementation_inserter(conn, task_id, packet.operation_id, packet.channel, config.run_id,
                                                         str(path), generator, build_context=build_context)
                if status != "compiled":
                    raise ValueError("Operation implementation failed: " + status)
                upsert_native_java_artifact(conn, artifact_id=f"{config.run_id}:assembly_output:{task_id}", run_id=config.run_id,
                                            conversion_id=packet.operation_id, kind="xml_operation", logical_id=packet.operation_id,
                                            artifact_path=str(path), status="converted", compiles=True)
                # Dependency additions change Gate 2 evidence. The final assembly hash
                # uses current component fingerprints so it can be reused after reapproval.
                current = collect_component_evidence(conn, config, profile)
                for component in payload["components"]:
                    match = next((value for value in current if value["task_id"] == component["task_id"] and
                                  value["converted_source"] == component["java_source"]), None)
                    if match:
                        component["fingerprint"] = match["fingerprint"]
                digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                conn.execute("""INSERT INTO operation_assembly_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id,operation_id,channel) DO UPDATE SET input_hash=excluded.input_hash,
                    service_path=excluded.service_path, service_hash=excluded.service_hash, pom_hash=excluded.pom_hash""",
                    (config.run_id, packet.operation_id, packet.channel, digest, str(path), _hash(path), _hash(Path(build_context.pom_path))))
                conn.commit()
                outcomes.append(dict(item, status="assembled", service_path=str(path), reused=False))
            except Exception as exc:
                attempts += 1
                upsert_agent_task(conn, task_id=task_id, run_id=config.run_id, agent_name="ManagedAssembly",
                                  scope_type="operation", scope_id=packet.operation_id, channel=packet.channel,
                                  target_language="java", status="blocked" if attempts >= config.max_agent_task_retries else "failed",
                                  attempt_number=attempts, max_retries=config.max_agent_task_retries,
                                  error_message=str(exc), input_data=payload)
                outcomes.append(dict(item, status="blocked", reason=str(exc)))
    write_run_report(directory, "assembly_results.json", json.dumps(outcomes, indent=2))
    if not outcomes or any(item["status"] != "assembled" for item in outcomes):
        update_run_status(conn, config.run_id, "blocked", "assembly_blocked")
        return "assembly_blocked"
    if gate_checker() != "assembly_pending":
        return "component_gate_not_accepted"
    update_run_status(conn, config.run_id, "paused", "operation_review_pending")
    return "operation_review_pending"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
