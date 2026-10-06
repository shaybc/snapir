"""Stage immutable approved sources and generate final managed Maven services."""

import hashlib
import json
import shutil
from pathlib import Path

from models.maven_dependency import MavenDependency
from runtime.human_gates import evaluate_gate
from runtime.managed_projects import create_build_context
from runtime.model_execution.adk_executor import AdkExecutor
from runtime.operation_review import run_operation_review_gate
from runtime.operation_review.evidence import collect_operation_evidence
from runtime.service_generation.project_output import configure_executable_build, validate_wrapper_output
from runtime.service_generation.validation import validate_service_project
from runtime.service_generation.corrections import route_correction
from tools.maven_dependency_tools.pom_manager import merge_dependencies
from tools.state_store_tools.agent_tasks import upsert_agent_task
from tools.state_store_tools.generated_artifacts import upsert_generated_artifact
from tools.state_store_tools.runs import update_run_status


def _project_hash(project):
    """Fingerprint build inputs without transient Maven output or audit files."""
    files = [Path(project) / "pom.xml", *sorted((Path(project) / "src").rglob("*"))]
    return hashlib.sha256(json.dumps([(str(path.relative_to(project)), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in files if path.is_file()], sort_keys=True).encode()).hexdigest()


def run_service_generation(conn, config, profile, plan, directory, *, gate_checker=None,
                           context_factory=create_build_context, generator=None, validator=validate_service_project):
    """Generate each selected service with durable attempts, then persist honest validation evidence."""
    gate_checker = gate_checker or (lambda: run_operation_review_gate(conn, config, profile, plan, directory))
    if gate_checker() != "service_generation_pending":
        return "operation_gate_not_accepted"
    report = (Path(directory) / "gate_3_report.txt").read_text(encoding="utf-8")
    if evaluate_gate(conn, config.run_id, 3, report, "human", True) != "approved":
        return "operation_gate_not_accepted"
    conn.execute("""CREATE TABLE IF NOT EXISTS service_generation_checkpoints (
        run_id TEXT, operation_id TEXT, channel TEXT, input_hash TEXT, project_hash TEXT,
        attempts INTEGER NOT NULL, validation_json TEXT, PRIMARY KEY(run_id,operation_id,channel))""")
    conn.commit()
    update_run_status(conn, config.run_id, "in_progress", "service_generation")
    outcomes = []
    correction_phase = None
    retry_generation = False
    for item in collect_operation_evidence(conn, config, profile, plan):
        key = (config.run_id, item["operation_id"], item["channel"])
        project = Path(directory) / "services" / item["channel"] / item["operation_id"]
        task_id = "service-" + hashlib.sha256(":".join(key).encode()).hexdigest()
        identity = hashlib.sha256((item["fingerprint"] + report).encode()).hexdigest()
        row = conn.execute("SELECT * FROM service_generation_checkpoints WHERE run_id=? AND operation_id=? AND channel=?", key).fetchone()
        attempts = row["attempts"] if row and row["input_hash"] == identity else 0
        result = None
        output = None
        try:
            if item["issues"]:
                raise ValueError("; ".join(item["issues"]))
            cached = json.loads(row["validation_json"]) if row else {}
            if (row and row["input_hash"] == identity and row["project_hash"] and
                    cached.get("package_passed") and cached.get("test_status") in {"passed", "not_available"} and
                    _project_hash(project) == row["project_hash"]):
                result = json.loads(row["validation_json"])
            else:
                if attempts >= config.max_agent_task_retries:
                    raise ValueError("Service generation retry limit reached")
                attempts += 1
                conn.execute("INSERT OR REPLACE INTO service_generation_checkpoints VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (*key, identity, "", attempts, "{}"))
                conn.commit()
                protected = {str(path.relative_to(item["project"])).replace("\\", "/"): path.read_text(encoding="utf-8")
                             for path in (Path(item["project"]) / "src/main/java").rglob("*.java")}
                # Only this runtime-owned final workspace is reset; reviewed projects remain intact.
                if project.exists():
                    if not project.resolve().is_relative_to((Path(directory) / "services").resolve()) or project.is_symlink():
                        raise ValueError("Unsafe final project path")
                    shutil.rmtree(project)
                project.mkdir(parents=True)
                shutil.copyfile(Path(item["project"]) / "pom.xml", project / "pom.xml")
                context = context_factory(profile, project, item["operation_id"])
                payload = dict(operation=item["payload"], approved_sources=protected,
                               pom=(project / "pom.xml").read_text(encoding="utf-8"),
                               validation_feedback=cached if row and row["input_hash"] == identity else {})
                previous = conn.execute("SELECT output_json FROM agent_tasks WHERE task_id=?", (task_id,)).fetchone()
                if previous and row and row["input_hash"] == identity:
                    payload["previous_generation"] = json.loads(previous[0]).get("generation_output")
                if generator is None:
                    if profile.model_provider == "mock":
                        raise ValueError("Mock service generation requires explicit fixtures")
                    output = AdkExecutor(profile).execute(
                        'Generate Spring Boot wrappers and tests around the supplied immutable Java sources. Address all validation_feedback using previous_generation when supplied. Return JSON with files (relative source/resource path to content) and dependencies (group_id, artifact_id, version, scope, reason, required_classes). Do not return a POM, binary files or alter approved sources. Include Application.java, controller, xml/JaxbConfig.java, error/GlobalExceptionHandler.java and application.properties. Delegate business logic to the supplied service. Use pinned verified Maven dependency proposals.',
                        json.dumps(payload))
                    output = json.loads(output)
                else:
                    output = generator(payload)
                proposals = [MavenDependency.model_validate(value) for value in output["dependencies"]]
                merge_dependencies(context.pom_path, proposals, context.verifier,
                                   allowed_ibm_artifacts=context.allowed_ibm_artifacts, task_id=task_id)
                wrappers = validate_wrapper_output(output["files"], protected, item["operation_id"], context)
                configure_executable_build(context)
                for name, content in {**protected, **wrappers}.items():
                    target = project / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")
                for name in protected:
                    shutil.copyfile(Path(item["project"]) / name, project / name)
                result = validator(project, context)
                result["generation_output"] = output
                conn.execute("UPDATE service_generation_checkpoints SET project_hash=?, validation_json=? WHERE run_id=? AND operation_id=? AND channel=?",
                             (_project_hash(project), json.dumps(result), *key))
            passed = result.get("build_passed") and result.get("package_passed") and result.get("ibm_guard_passed") and result.get("test_status") == "passed"
            upsert_generated_artifact(conn, artifact_id=task_id, run_id=config.run_id, operation_id=item["operation_id"],
                channel=item["channel"], target_language="java", artifact_kind="service", generated_path=str(project),
                status="converted" if passed else "blocked", blocking_reason=None if passed else "validation_incomplete",
                attempt_number=attempts)
        except Exception as exc:
            result = dict(error=str(exc), build_passed=False, generation_output=output)
            passed = False
        if not passed:
            conn.execute("UPDATE service_generation_checkpoints SET validation_json=? WHERE run_id=? AND operation_id=? AND channel=?",
                         (json.dumps(result), *key))
            route = route_correction(conn, config, item, result) if not item["issues"] else "human"
            result["correction_route"] = route
            if route == "component":
                correction_phase = "component_correction_pending"
            elif route == "assembly" and correction_phase != "component_correction_pending":
                correction_phase = "assembly_correction_pending"
            elif route == "generation" and attempts < config.max_agent_task_retries:
                retry_generation = True
        upsert_agent_task(conn, task_id=task_id, run_id=config.run_id, agent_name="ManagedServiceGeneration",
            scope_type="operation", scope_id=item["operation_id"], channel=item["channel"], target_language="java",
            status="completed" if passed else "blocked", input_data=dict(fingerprint=identity), output_data=result,
            max_retries=config.max_agent_task_retries)
        outcomes.append(dict(operation_id=item["operation_id"], channel=item["channel"], project=str(project),
                             passed=bool(passed), validation=result))
        conn.commit()
    fresh = collect_operation_evidence(conn, config, profile, plan)
    expected = [(value["operation_id"], value["channel"],
                 hashlib.sha256((value["fingerprint"] + report).encode()).hexdigest()) for value in fresh]
    recorded = conn.execute("SELECT operation_id,channel,input_hash FROM service_generation_checkpoints WHERE run_id=?",
                            (config.run_id,)).fetchall()
    unchanged = set(expected) == {tuple(value) for value in recorded} and all(not value["issues"] for value in fresh)
    phase = "validation_evidence_pending" if unchanged and outcomes and all(value["passed"] for value in outcomes) else "service_generation_blocked"
    if correction_phase:
        phase = correction_phase
    (Path(directory) / "service_validation_results.json").write_text(json.dumps(outcomes, indent=2), encoding="utf-8")
    update_run_status(conn, config.run_id, "paused" if phase == "validation_evidence_pending" else "blocked", phase)
    if retry_generation and not correction_phase:
        return run_service_generation(conn, config, profile, plan, directory, gate_checker=gate_checker,
            context_factory=context_factory, generator=generator, validator=validator)
    return phase
