"""Persist component reviews, route bounded revisions, and enforce Human Gate 2."""

from runtime.workspace_paths import run_report_path, write_run_report
import json
from pathlib import Path
import hashlib

from agents.source_conversion.native_java_reviewer.agent import build_human_gate2_report
from models.conversion_models import ConversionReviewResult
from runtime.component_review.evidence import collect_component_evidence
from runtime.component_review.reviewer import review_component
from runtime.human_gates import evaluate_gate
from tools.state_store_tools._json import utc_now
from tools.state_store_tools.runs import update_run_status


def run_component_review_gate(conn, config, profile, plan, directory, *, model_reviewer=None,
                              project_builder=None, conversion_runner=None) -> str:
    """Stop at unresolved reviews or Gate 2; expose assembly_pending only on acceptance.

    Injected reviewer/build/conversion functions support deterministic integration
    tests. Production defaults use configured ADK and managed Maven execution.
    """
    conn.execute("""CREATE TABLE IF NOT EXISTS component_review_snapshots (
        task_id TEXT NOT NULL, fingerprint TEXT NOT NULL, result_json TEXT NOT NULL,
        updated_at TEXT NOT NULL, PRIMARY KEY(task_id, fingerprint))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS component_revision_attempts (
        task_id TEXT PRIMARY KEY, attempts INTEGER NOT NULL)""")
    conn.commit()
    if conversion_runner is None:
        from runtime.managed_projects import run_managed_tasks
        conversion_runner = lambda: run_managed_tasks(conn, config, profile, plan)
    if project_builder is None:
        from runtime.managed_projects import create_build_context
        def project_builder(project):
            from constants import COMMON_LIB_ARTIFACT_ID
            import tempfile
            import shutil
            context = create_build_context(profile, Path(project), COMMON_LIB_ARTIFACT_ID if Path(project).name == "common-lib" else Path(project).name)
            # Assembly-owned files must not prevent retrying a failed assembly.
            # Gate 2 builds exactly its reviewed components, using the same POM.
            with tempfile.TemporaryDirectory(prefix="snapir-component-build-") as temporary:
                staged = Path(temporary) / Path(project).name
                staged.mkdir()
                shutil.copy2(context.pom_path, staged / "pom.xml")
                for component in evidence:
                    if component["project"] == project and component["source_path"]:
                        original = Path(component["source_path"])
                        destination = staged / original.relative_to(Path(project))
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(original, destination)
                result = context.verifier.compile_project(staged, context.allowed_ibm_artifacts,
                                                           goal="install" if Path(project).name == "common-lib" or Path(project).parent.name == "libraries" else "compile")
            return result.returncode == 0
    # Each revision consumes a persisted attempt; resume cannot reset the bound.
    while True:
        evidence = collect_component_evidence(conn, config, profile)
        results = []
        revised = False
        for item in evidence:
            if item["issues"]:
                result = ConversionReviewResult(conversion_id=item["conversion_id"], issues=item["issues"],
                                                confidence="low", review_status="needs_human_review")
            else:
                cached = conn.execute("SELECT result_json FROM component_review_snapshots WHERE task_id=? AND fingerprint=?",
                                      (item["task_id"], item["fingerprint"])).fetchone()
                try:
                    result = ConversionReviewResult.model_validate_json(cached[0]) if cached else review_component(item, profile, model_reviewer)
                except Exception as exc:
                    result = ConversionReviewResult(conversion_id=item["conversion_id"], issues=["Component review failed: " + type(exc).__name__],
                                                    confidence="low", review_status="needs_human_review")
                conn.execute("""INSERT INTO component_review_snapshots VALUES (?, ?, ?, ?)
                    ON CONFLICT(task_id,fingerprint) DO UPDATE SET result_json=excluded.result_json, updated_at=excluded.updated_at""",
                    (item["task_id"], item["fingerprint"], result.model_dump_json(), utc_now()))
            if result.review_status == "needs_revision":
                row = conn.execute("SELECT attempts FROM component_revision_attempts WHERE task_id=?", (item["task_id"],)).fetchone()
                attempts = row[0] if row else 0
                limit = conn.execute("SELECT max_retries FROM agent_tasks WHERE task_id=?", (item["task_id"],)).fetchone()[0]
                if attempts < limit:
                    conn.execute("""INSERT INTO component_revision_attempts VALUES (?, ?) ON CONFLICT(task_id)
                        DO UPDATE SET attempts=excluded.attempts""", (item["task_id"], attempts + 1))
                    data = item["task_input"]
                    data["component_review_feedback"] = result.issues
                    data["previous_converted_source"] = item["converted_source"]
                    conn.execute("UPDATE agent_tasks SET status='pending', input_json=?, updated_at=? WHERE task_id=?",
                                 (json.dumps(data), utc_now(), item["task_id"]))
                    revised = True
                else:
                    result = result.model_copy(update=dict(review_status="needs_human_review",
                                                           issues=[*result.issues, "Component revision limit reached"]))
            conn.execute("UPDATE native_java_artifacts SET review_status=?, review_notes_json=?, updated_at=? WHERE artifact_id=? AND run_id=?",
                         (result.review_status, json.dumps(result.issues), utc_now(), item["artifact_id"], config.run_id))
            results.append(result)
        conn.commit()
        if revised:
            update_run_status(conn, config.run_id, "in_progress", "component_revision")
            try:
                outcome = conversion_runner()
            except Exception:
                outcome = {"failed": 1}
            if not outcome.get("failed"):
                continue
            # Recollect failed conversion evidence; its flags prevent gate passage.
            evidence = collect_component_evidence(conn, config, profile)
        break
    problems = [issue for item in evidence for issue in item["issues"]]
    from tools.state_store_tools.shared_library_plans import get_shared_library_plan
    library_plan = get_shared_library_plan(conn, config.run_id)
    if library_plan:
        problems.extend(library_plan.diagnostics)
    approved_scope = {(packet.operation_id, packet.channel) for batch in plan.batches for packet in batch.task_packets}
    from runtime.shared_libraries.ownership import task_covers
    for operation, channel in approved_scope:
        for row in conn.execute("SELECT implementation_id FROM java_dependency_uses WHERE run_id=? AND operation_id=? AND channel=?",
                                (config.run_id, operation, channel)):
            key = "implementation:" + row[0]
            if not any(item["task_input"].get("source_component_key") == key and task_covers(item["task_input"], operation, channel)
                       for item in evidence):
                problems.append("Expected Java utility conversion task is missing: " + key)
    for item in evidence:
        owner = item["task_input"].get("managed_project_operation")
        if owner is not None and (owner, item["task_input"].get("channel")) not in approved_scope:
            problems.append("Component owner is outside the approved migration plan: " + owner)
    reviewed_paths = {item["source_path"] for item in evidence if item["source_path"]}
    assembly_rows = conn.execute("""SELECT a.artifact_path,t.scope_id,t.channel FROM native_java_artifacts a
        JOIN agent_tasks t ON t.run_id=a.run_id AND t.scope_id=a.logical_id
        WHERE a.run_id=? AND a.kind='xml_operation' AND t.agent_name='ManagedAssembly'""", (config.run_id,)).fetchall()
    for assembly in assembly_rows:
        if assembly["artifact_path"]:
            path = Path(assembly["artifact_path"]).resolve()
            owned_root = (Path(config.output_root) / assembly["channel"] / assembly["scope_id"] / "src/main/java").resolve()
            if path.is_relative_to(owned_root):
                reviewed_paths.add(str(path))
    projects = {item["project"] for item in evidence} | {str((Path(config.output_root) / "common-lib").resolve())}
    for project in projects:
        for path in (Path(project) / "src/main/java").rglob("*.java"):
            if str(path.resolve()) not in reviewed_paths:
                problems.append("Generated Java source has no component review task: " + str(path))
    if not evidence:
        problems.append("No expected converted components are available for review")
    closures_path = run_report_path(directory, "dependency_closure.json")
    framework_components = set()
    if closures_path.exists():
        for closure in json.loads(closures_path.read_text(encoding="utf-8")):
            formats = closure.get("formats", {})
            tags = set(formats.get("formatter_tags", []))
            for chain in formats.get("decorator_chains", {}).values():
                tags.update(chain)
            for tag in tags:
                mappings = conn.execute("SELECT fqcn,channel FROM tag_registry WHERE run_id=? AND tag_name=? AND channel IN (?, 'XML')",
                                        (config.run_id, tag, closure["channel"])).fetchall()
                specific = {row["fqcn"] for row in mappings if row["channel"] == closure["channel"]}
                candidates = specific or {row["fqcn"] for row in mappings}
                if len(candidates) != 1:
                    problems.append("Framework component mapping is unresolved or ambiguous: " + tag)
                else:
                    framework_components.update(candidates)
                    if library_plan and not any(item["conversion_id"] in candidates and
                            task_covers(item["task_input"], closure["operation_id"], closure["channel"]) for item in evidence):
                        problems.append("Framework component conversion is missing for this operation: " + tag)
            requirements = [("ibm_java", reference["fqcn"]) for reference in closure.get("java_classes", [])]
            requirements += [("xml_fmtdef", name) for name in closure.get("formats", {}).get("all_format_ids", [])]
            if closure.get("context_id"):
                requirements.append(("xml_context", closure["context_id"]))
            for kind, logical_id in requirements:
                from runtime.shared_libraries.ownership import task_covers
                if not any(item["kind"] == kind and item["conversion_id"] == logical_id and
                           task_covers(item["task_input"], closure["operation_id"], closure["channel"])
                           for item in evidence):
                    problems.append("Expected conversion task is missing: " + logical_id)
    for fqcn in sorted(framework_components):
        if not any(item["kind"] == "ibm_java" and item["conversion_id"] == fqcn and
                   (library_plan is not None or item["task_input"].get("managed_project_operation") is None) for item in evidence):
            problems.append("Framework component conversion is missing: " + fqcn)
    builds = {}
    from runtime.shared_libraries.dependencies import ordered_review_projects
    for project in ordered_review_projects(conn, config, {item["project"] for item in evidence}):
        try:
            builds[project] = bool(project_builder(project))
        except Exception:
            builds[project] = False
    common = str((Path(config.output_root) / "common-lib").resolve())
    if common not in builds:
        try:
            builds[common] = bool(project_builder(common))
        except Exception:
            builds[common] = False
    passed = bool(results) and not problems and all(result.review_status == "approved" for result in results) and all(builds.values())
    project_hashes = {}
    for project in builds:
        try:
            project_hashes[project] = hashlib.sha256((Path(project) / "pom.xml").read_bytes()).hexdigest()
        except OSError:
            project_hashes[project] = "missing"
            passed = False
    report = build_human_gate2_report(results, common_lib_build_passed=builds.get(common, False),
                                      framework_tags_converted=sum(1 for fqcn in framework_components if any(
                                          item["conversion_id"] == fqcn and result.review_status == "approved"
                                          for item, result in zip(evidence, results))),
                                      sample_files=[item["source_path"] for item in evidence if item["source_path"]])
    report += json.dumps(dict(component_fingerprints=[dict(task_id=item["task_id"], fingerprint=item["fingerprint"],
                    source_hash=item["source_hash"], pom_hash=item["pom_hash"]) for item in evidence],
                    reviews=[result.model_dump(mode="json") for result in results], builds=builds,
                    project_pom_hashes=project_hashes, blockers=problems), sort_keys=True, indent=2)
    # Recheck contents after model and build calls; approval must cover unchanged evidence.
    fresh = collect_component_evidence(conn, config, profile)
    if [(item["task_id"], item["fingerprint"]) for item in fresh] != [(item["task_id"], item["fingerprint"]) for item in evidence]:
        passed = False
        report += "\nComponent evidence changed during review; repeat review."
    for project, digest in project_hashes.items():
        try:
            unchanged = hashlib.sha256((Path(project) / "pom.xml").read_bytes()).hexdigest() == digest
        except OSError:
            unchanged = False
        if not unchanged:
            passed = False
            report += "\nProject POM changed during review; repeat review."
    directory = Path(directory)
    write_run_report(directory, "gate_2_report.txt", report)
    decision = evaluate_gate(conn, config.run_id, 2, report, profile.gate_policies.get("2", "human"), passed)
    if decision == "approved":
        from runtime.shared_libraries.registry import register_approved_components
        register_approved_components(conn, config, profile, evidence)
    phase = "assembly_pending" if decision == "approved" else "component_review_blocked" if decision == "blocked" else f"gate_2_{decision}"
    update_run_status(conn, config.run_id, "stopped" if decision == "rejected" else "blocked" if decision == "blocked" else "paused", phase)
    return phase
