"""Create canonical Maven projects and route existing conversion tasks to them."""

import logging
import json
import re
import hashlib
from pathlib import Path

from constants import COMMON_LIB_ARTIFACT_ID, COMMON_LIB_GROUP_ID, JAVA_VERSION, JAVA_PACKAGE_BASE
from runtime.model_execution.adk_executor import AdkExecutor
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tools.maven_dependency_tools.build_invalidation import reconcile_pom_hash
from tools.maven_dependency_tools.pom_manager import initialize_managed_pom
from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier
from tools.state_store_tools._json import loads
from runtime.managed_conversion_response import managed_instruction, parse_managed_response
from runtime.java_public_type import converted_java_identity


def create_build_context(profile, project_root: Path, artifact_id: str) -> ManagedBuildContext:
    """Initialize one managed project using the user's Maven configuration."""
    verifier = MavenRepositoryVerifier(profile.maven_settings_path, profile.approved_maven_repository_urls,
                                       profile.maven_local_repository)
    from runtime.java_toolchain import java_environment
    verifier.environment = java_environment(getattr(profile, "java_version", int(JAVA_VERSION)),
                                          getattr(profile, "java_home", None))
    pom = project_root / "pom.xml"
    initialize_managed_pom(str(pom), COMMON_LIB_GROUP_ID, artifact_id,
                           java_version=getattr(profile, "java_version", int(JAVA_VERSION)))
    retained = [rule for rule in getattr(profile, "external_dependencies", []) if rule.treatment == "retain"]
    return ManagedBuildContext(str(pom), verifier,
        tuple(dict.fromkeys([*profile.allowed_ibm_artifacts, *(rule.maven_coordinates for rule in retained if rule.maven_coordinates)])),
        tuple(dict.fromkeys([*profile.allowed_ibm_classes, *(rule.class_name for rule in retained if rule.class_name)])))


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
    from runtime.shared_libraries.projects import create_library_contexts
    libraries = create_library_contexts(conn, config, profile, contexts, create_build_context)
    for shared in libraries.values():
        reconcile_pom_hash(conn, config.run_id, shared.pom_path, None, "all")
    rows = conn.execute("""SELECT * FROM agent_tasks WHERE run_id=? AND
        status IN ('pending','failed','needs_rerun') ORDER BY created_at""", (config.run_id,)).fetchall()
    results = {"compiled": 0, "failed": 0, "pending": 0}
    executor = AdkExecutor(profile)
    from runtime.shared_libraries.dependencies import ordered_conversion_tasks, converted_dependency_apis, dependency_binding
    rows = ordered_conversion_tasks(conn, config, rows)
    from runtime.composer_behavior_context import attach_composer_behavior
    common_installed = False
    installed_libraries = set()
    conversion_rows = [row for row in rows if (loads(row["input_json"], {}) or {}).get("kind") in {"ibm_java", "xml_fmtdef", "xml_context"}]
    for position, row in enumerate(conversion_rows, 1):
        executor.component_label = f"Component {position}/{len(conversion_rows)}: {row['scope_id']}"
        logging.getLogger(__name__).info("%s", executor.component_label)
        data = loads(row["input_json"], {}) or {}
        kind = data.get("kind")
        if kind not in {"ibm_java", "xml_fmtdef", "xml_context"}:
            continue
        data = attach_composer_behavior(data)
        owner = data.get("managed_project_operation")
        context = contexts.get((owner, row["channel"])) if owner else libraries.get(data.get("managed_library_id") or "common-lib")
        if context is None:
            raise ValueError("Conversion task references an operation outside the approved plan")
        retained = [item for item in data.get("external_dependencies", []) if item["treatment"] == "retain"]
        context.allowed_ibm_classes = tuple(dict.fromkeys([*context.allowed_ibm_classes, *(item["class_name"] for item in retained)]))
        context.allowed_ibm_artifacts = tuple(dict.fromkeys([*context.allowed_ibm_artifacts, *(item["maven_coordinates"] for item in retained if item.get("maven_coordinates"))]))
        from tools.state_store_tools.shared_library_plans import get_shared_library_plan
        library_plan = get_shared_library_plan(conn, config.run_id)
        if not owner and library_plan:
            from tools.common_lib_tools.build import run_common_lib_build
            for dependency in library_plan.library_dependencies.get(data.get("managed_library_id"), []):
                if dependency not in installed_libraries:
                    build = run_common_lib_build(str(Path(libraries[dependency].pom_path).parent), build_context=libraries[dependency])
                    if not build.success:
                        results["failed"] += 1
                        return results
                    installed_libraries.add(dependency)
        if owner and not common_installed:
            if results["failed"]:
                return results
            from tools.common_lib_tools.build import run_common_lib_build
            order = library_plan.library_build_order if library_plan and library_plan.library_build_order else list(libraries)
            for name in [*order, *(name for name in libraries if name not in order)]:
                shared = libraries[name]
                build = run_common_lib_build(str(Path(shared.pom_path).parent), build_context=shared)
                if not build.success:
                    results["failed"] += 1
                    return results
            common_installed = True
        try:
            current_dependencies = dependency_binding(conn, config, data.get("source_component_key"), data.get("external_dependencies", []))
            if current_dependencies.get("dependency_source_hash") != data.get("dependency_source_hash"):
                raise ValueError("Conversion dependency inputs changed; reschedule conversion")
            data["converted_dependency_apis"] = converted_dependency_apis(conn, config, data)
        except ValueError as exc:
            from tools.state_store_tools.agent_tasks import update_task_status
            from runtime.shared_libraries.dependencies import UtilityNotReadyError
            update_task_status(conn, row["task_id"], "pending" if isinstance(exc, UtilityNotReadyError) else "blocked", error_message=str(exc))
            results["failed"] += 1
            continue
        conn.execute("UPDATE agent_tasks SET input_json=? WHERE task_id=?", (json.dumps(data), row["task_id"]))
        conn.execute("UPDATE agent_tasks SET status='pending' WHERE task_id=?", (row["task_id"],))
        conn.commit()
        from runtime.shared_libraries.registry import reusable_component
        reused = reusable_component(conn, config, profile, data, context)
        if reused:
            from tools.state_store_tools.native_java_artifacts import upsert_native_java_artifact
            from tools.state_store_tools.agent_tasks import update_task_status
            compiled = context.verifier.compile_project(Path(context.pom_path).parent, context.allowed_ibm_artifacts)
            if compiled.returncode:
                results["failed"] += 1
                continue
            upsert_native_java_artifact(conn, artifact_id=f"{config.run_id}:native_java:{row['task_id']}",
                run_id=config.run_id, conversion_id=data["conversion_id"], kind=kind, logical_id=data["conversion_id"],
                artifact_path=reused["source_path"], compiles=True, review_status="approved", status="converted")
            update_task_status(conn, row["task_id"], "completed")
            results["compiled"] += 1
            results["reused"] = results.get("reused", 0) + 1
            continue
        instruction = {"ibm_java": MANAGED_IBM_CLEANER_INSTRUCTION,
                       "xml_fmtdef": XML_TO_JAVA_INSTRUCTION,
                       "xml_context": CONTEXT_TO_JAVA_INSTRUCTION}[kind]
        instruction = managed_instruction(instruction, kind)
        instruction += f"\nTarget Java version: {profile.java_version}. Generate code compatible with this version."
        instruction += "\nApproved IBM client classes: " + json.dumps(list(context.allowed_ibm_classes))
        if data.get("converted_dependency_apis"):
            instruction += "\nUse the supplied converted_dependency_apis for original Java utility dependencies. Call their actual native APIs; do not recreate or rename their implementations in this component."
        if data.get("component_review_feedback"):
            instruction += "\nRevise the previous converted source to address every component_review_feedback issue in the request. Preserve original business behavior."
        instruction = instruction.replace("Remove ALL imports starting with com.ibm.*", "Remove IBM runtime imports except explicitly approved IBM client classes; remove imports starting with com.ibm.* when not approved")
        values = {"java_source": data["primary_source_content"], "fields_json": data["primary_source_content"],
                  "context_id": row["scope_id"], "format_id": row["scope_id"], "java_package_base": JAVA_PACKAGE_BASE}
        instruction = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}",
                             lambda match: values.get(match.group(1), "See the supplied task JSON"), instruction)
        if profile.model_provider == "mock":
            raise ValueError("Mock conversion requires explicit fixtures; synthetic conversion is not supported")
        try:
            from runtime.composer_replacement_validation import validate_composer_replacements
            request = dict(data)
            for correction in range(profile.max_model_attempts):
                output = executor.execute(instruction, json.dumps(request))
                try:
                    source = parse_managed_response(output, kind)
                except ValueError as exc:
                    if correction + 1 == profile.max_model_attempts:
                        raise
                    request.update(previous_model_response=output, response_correction_feedback=str(exc))
                    logging.getLogger(__name__).warning("%s - requesting correction for invalid response JSON or schema: %s", executor.component_label, exc)
                    continue
                package_name, type_name = converted_java_identity(source, data["primary_source_content"] if kind == "ibm_java" else None)
                try:
                    validate_composer_replacements(source, data.get("external_dependencies", []))
                    break
                except ValueError as exc:
                    if correction + 1 == profile.max_model_attempts:
                        raise
                    request.update(previous_converted_source=source, replacement_correction_feedback=str(exc))
                    logging.getLogger(__name__).warning("%s - requesting correction for unresolved framework replacements: %s", executor.component_label, exc)
        except Exception as exc:
            from tools.state_store_tools.agent_tasks import update_task_status
            from runtime.model_execution.error_details import sanitize_diagnostic
            update_task_status(conn, row["task_id"], "failed", error_message=sanitize_diagnostic(str(exc)))
            raise
        source_path = context.source_root / Path(*package_name.split(".")) / (type_name + ".java")
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
        from tools.conversion_tools.conversion_component_set import checked_conversion_units
        units, source_files = checked_conversion_units(closure)
        from runtime.composer_behavior_context import required_composer_behavior
        required_evidence = required_composer_behavior()
        # Contexts and DTOs precede implementation classes in the task queue.
        units.sort(key=lambda unit: {"xml_context": 0, "xml_fmtdef": 1, "ibm_java": 2}[unit[0]])
        for kind, logical_id, source, shared in units:
            from runtime.shared_libraries.ownership import task_binding
            source_file = source_files.get(logical_id)
            binding = task_binding(conn, config, closure, kind, logical_id, source_file)
            from runtime.shared_libraries.dependencies import dependency_binding
            binding.update(dependency_binding(conn, config, binding.get("source_component_key"), closure.get("external_dependencies", [])))
            source = binding.pop("configured_source_xml", source)
            if binding:
                shared = binding["managed_library_id"] is not None
            owner = None if shared else closure["operation_id"]
            identity = (f"{config.run_id}:{binding['source_component_key']}:{binding['managed_library_id'] or closure['channel'] + '/' + closure['operation_id']}"
                        if binding else f"{config.run_id}:{closure['channel']}:{owner}:{kind}:{logical_id}")
            task_id = "managed-" + hashlib.sha256(identity.encode()).hexdigest()
            existing = get_agent_task(conn, task_id)
            if existing is not None:
                original = existing["input_json"] or {}
                if original.get("primary_source_content") == source and original.get("source_component_hash") == binding.get("source_component_hash") and original.get("dependency_source_hash") == binding.get("dependency_source_hash") and original.get("external_dependencies", []) == closure.get("external_dependencies", []) and original.get("composer_behavior_evidence") == required_evidence:
                    continue
            data = ConversionTaskPacket(conversion_id=logical_id, kind=kind, channel=closure["channel"],
                                        primary_source_content=source, relationship_context=json.dumps(closure),
                                        target_kind="native_java").model_dump(mode="json")
            data["managed_project_operation"] = owner
            data["external_dependencies"] = closure.get("external_dependencies", [])
            data["composer_behavior_evidence"] = required_evidence
            data.update(binding)
            if shared and binding:
                data["relationship_context"] = json.dumps(dict(component=binding["source_component_key"], consumers=binding["consumer_operations"]), sort_keys=True)
            upsert_agent_task(conn, task_id=task_id, run_id=config.run_id, agent_name="ManagedConversion",
                              scope_type="java_class", scope_id=logical_id, channel=closure["channel"],
                              target_language="java", status="pending", input_data=data,
                              max_retries=config.max_agent_task_retries)
