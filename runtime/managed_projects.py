"""Create canonical Maven projects and route existing conversion tasks to them."""

import json
import re
import hashlib
from pathlib import Path

from constants import COMMON_LIB_ARTIFACT_ID, COMMON_LIB_GROUP_ID
from runtime.model_execution.adk_executor import AdkExecutor
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tools.maven_dependency_tools.build_invalidation import reconcile_pom_hash
from tools.maven_dependency_tools.pom_manager import initialize_managed_pom
from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier
from tools.state_store_tools._json import loads


def create_build_context(profile, project_root: Path, artifact_id: str) -> ManagedBuildContext:
    """Initialize one managed project using the configured target repository policy."""
    if not profile.maven_settings_path or not profile.maven_local_repository:
        raise ValueError("Managed builds require maven_settings_path and maven_local_repository")
    verifier = MavenRepositoryVerifier(profile.maven_settings_path, profile.approved_maven_repository_urls,
                                       profile.maven_local_repository)
    pom = project_root / "pom.xml"
    initialize_managed_pom(str(pom), COMMON_LIB_GROUP_ID, artifact_id)
    return ManagedBuildContext(str(pom), verifier, tuple(profile.allowed_ibm_artifacts), tuple(profile.allowed_ibm_classes))


def run_managed_tasks(conn, config, profile, plan) -> dict[str, int]:
    """Dispatch pending conversion tasks into their operation or shared-library POM.

    Tasks carry managed_project_operation in input_json to identify their owner;
    shared tasks use an empty owner. Task creation remains the closure scheduler's
    responsibility. No successful conversion is inferred from an empty task queue.
    """
    from agents.source_conversion.ibm_java_cleaner.agent import MANAGED_IBM_CLEANER_INSTRUCTION, run_ibm_java_cleaner_task
    from agents.source_conversion.context_to_java_converter.agent import CONTEXT_TO_JAVA_INSTRUCTION, run_context_to_java_converter_task
    from agents.source_conversion.xml_to_java_converter.agent import XML_TO_JAVA_INSTRUCTION, run_xml_to_java_converter_task

    contexts = {}
    for batch in plan.batches:
        for packet in batch.task_packets:
            identity = (packet.operation_id, packet.channel)
            context = create_build_context(profile, Path(config.output_root) / packet.channel / packet.operation_id,
                                           packet.operation_id)
            contexts[identity] = context
            reconcile_pom_hash(conn, config.run_id, context.pom_path, packet.operation_id, packet.channel)
    shared = create_build_context(profile, Path(config.output_root) / "common-lib", COMMON_LIB_ARTIFACT_ID)
    from models.maven_dependency import MavenDependency
    from tools.maven_dependency_tools.pom_manager import merge_dependencies
    for context in contexts.values():
        merge_dependencies(context.pom_path, [MavenDependency(
            group_id=COMMON_LIB_GROUP_ID, artifact_id=COMMON_LIB_ARTIFACT_ID, version="1.0.0",
            reason="Generated common-library module from this migration run")],
            lambda proposal: None, task_id="generated-common-library-baseline")
    reconcile_pom_hash(conn, config.run_id, shared.pom_path, None, "all")
    rows = conn.execute("""SELECT * FROM agent_tasks WHERE run_id=? AND
        status IN ('pending','failed','needs_rerun') ORDER BY created_at""", (config.run_id,)).fetchall()
    results = {"compiled": 0, "failed": 0, "pending": 0}
    executor = AdkExecutor(profile)
    rows = sorted(rows, key=lambda row: bool((loads(row["input_json"], {}) or {}).get("managed_project_operation")))
    common_installed = False
    for row in rows:
        data = loads(row["input_json"], {}) or {}
        kind = data.get("kind")
        if kind not in {"ibm_java", "xml_fmtdef", "xml_context"}:
            continue
        owner = data.get("managed_project_operation")
        context = contexts.get((owner, row["channel"])) if owner else shared
        if context is None:
            raise ValueError("Conversion task references an operation outside the approved plan")
        if owner and not common_installed:
            if results["failed"]:
                return results
            from tools.common_lib_tools.build import run_common_lib_build
            build = run_common_lib_build(str(Path(shared.pom_path).parent), build_context=shared)
            if not build.success:
                results["failed"] += 1
                return results
            common_installed = True
        conn.execute("UPDATE agent_tasks SET status='pending' WHERE task_id=?", (row["task_id"],))
        conn.commit()
        instruction = {"ibm_java": MANAGED_IBM_CLEANER_INSTRUCTION,
                       "xml_fmtdef": XML_TO_JAVA_INSTRUCTION,
                       "xml_context": CONTEXT_TO_JAVA_INSTRUCTION}[kind]
        instruction += "\nReturn JSON with java_source and dependencies (group_id, artifact_id, version, scope, reason, required_classes)."
        if kind == "xml_fmtdef":
            instruction += " Include service_layer_requirements in the same JSON object, without markers."
        instruction += "\nApproved IBM client classes: " + json.dumps(profile.allowed_ibm_classes)
        if data.get("component_review_feedback"):
            instruction += "\nRevise the previous converted source to address every component_review_feedback issue in the request. Preserve original business behavior."
        instruction = instruction.replace("Remove ALL imports starting with com.ibm.*", "Remove IBM runtime imports except explicitly approved IBM client classes; remove imports starting with com.ibm.* when not approved")
        values = {"java_source": data["primary_source_content"], "fields_json": data["primary_source_content"],
                  "context_id": row["scope_id"], "format_id": row["scope_id"]}
        instruction = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}",
                             lambda match: values.get(match.group(1), "See the supplied task JSON"), instruction)
        if profile.model_provider == "mock":
            raise ValueError("Mock conversion requires explicit fixtures; synthetic conversion is not supported")
        output = executor.execute(instruction, json.dumps(data))
        source = json.loads(output)["java_source"]
        package = re.search(r"\bpackage\s+([\w.]+)\s*;", source)
        declaration = re.search(r"\bpublic\s+(?:final\s+)?class\s+(\w+)", source)
        if not declaration:
            raise ValueError("Conversion must return one named public Java class")
        source_path = context.source_root / Path(*(package.group(1).split(".") if package else [])) / (declaration.group(1) + ".java")
        callback = lambda packet, response=output: response
        if kind == "ibm_java":
            result = run_ibm_java_cleaner_task(conn, row["task_id"], str(source_path), config.run_id,
                                              callback, build_context=context)
        elif kind == "xml_fmtdef":
            result = run_xml_to_java_converter_task(conn, row["task_id"], str(source_path), config.run_id,
                                                    callback, build_context=context)
        else:
            result = run_context_to_java_converter_task(conn, row["task_id"], row["scope_id"], row["channel"],
                                                        config.run_id, str(source_path), callback, build_context=context)
        reconcile_pom_hash(conn, config.run_id, context.pom_path, owner, row["channel"],
                          exclude_task_id=row["task_id"] if result == "compiled" else "")
        results["compiled" if result == "compiled" else "failed"] += 1
    if not results["compiled"] and not results["failed"]:
        results["pending"] = 1
    return results


def enqueue_closure_conversions(conn, config, closures):
    """Create component tasks from READY closures without duplicating completed work."""
    from models.conversion_models import ConversionTaskPacket
    from tools.state_store_tools.agent_tasks import get_agent_task, upsert_agent_task

    for closure in closures:
        if closure["status"] != "READY":
            continue
        units = []
        if closure.get("context_id"):
            units.append(("xml_context", closure["context_id"], json.dumps(closure.get("context_fields", [])), False))
        for reference in closure.get("java_classes", []):
            units.append(("ibm_java", reference["fqcn"], Path(reference["source_file"]).read_text(encoding="utf-8"), reference["shared"]))
        for format_id in closure["formats"].get("all_format_ids", []):
            row = conn.execute("SELECT source_path FROM source_artifacts WHERE run_id=? AND kind='format' AND logical_id=?",
                               (config.run_id, format_id)).fetchone()
            if row is None:
                raise ValueError("READY closure references a missing format")
            units.append(("xml_fmtdef", format_id, Path(row[0]).read_text(encoding="utf-8"),
                          format_id in closure.get("shared_formats", [])))
        # Contexts and DTOs precede implementation classes in the task queue.
        units.sort(key=lambda unit: {"xml_context": 0, "xml_fmtdef": 1, "ibm_java": 2}[unit[0]])
        for kind, logical_id, source, shared in units:
            owner = None if shared else closure["operation_id"]
            identity = f"{config.run_id}:{closure['channel']}:{owner}:{kind}:{logical_id}"
            task_id = "managed-" + hashlib.sha256(identity.encode()).hexdigest()
            if get_agent_task(conn, task_id) is not None:
                continue
            data = ConversionTaskPacket(conversion_id=logical_id, kind=kind, channel=closure["channel"],
                                        primary_source_content=source, relationship_context=json.dumps(closure),
                                        target_kind="native_java").model_dump(mode="json")
            data["managed_project_operation"] = owner
            upsert_agent_task(conn, task_id=task_id, run_id=config.run_id, agent_name="ManagedConversion",
                              scope_type="java_class", scope_id=logical_id, channel=closure["channel"],
                              target_language="java", status="pending", input_data=data,
                              max_retries=config.max_agent_task_retries)
