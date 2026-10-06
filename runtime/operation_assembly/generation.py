"""Adapt ADK output to managed skeleton and one-method implementation passes."""

import json
import re
from pathlib import Path

from agents.operation_assembly.service_skeleton_generator.agent import SKELETON_INSTRUCTION
from agents.operation_assembly.step_implementation_inserter.agent import IMPLEMENTATION_PASS_INSTRUCTION, PASSES, replace_method_body
from models.maven_dependency import JavaConversionOutput
from runtime.model_execution.adk_executor import AdkExecutor
from tools.java_analysis_tools.java_slicer import extract_method
from tools.maven_dependency_tools.pom_manager import merge_dependencies


def generate_skeleton(profile, payload) -> JavaConversionOutput:
    """Request a structured skeleton using actual converted component types."""
    if profile.model_provider == "mock":
        raise ValueError("Mock assembly requires explicit generation fixtures")
    instruction = re.sub(r"\{[A-Za-z_][A-Za-z0-9_]*\}", "See assembly input JSON", SKELETON_INSTRUCTION)
    instruction += "\nReturn JSON with java_source and dependencies (group_id, artifact_id, version, scope, reason, required_classes)."
    instruction += "\nUse the actual supplied DTO/context class names, packages, and method signatures, rather than inferred names."
    instruction += "\nGenerate the requested public service class. Do not fabricate collaborators or their APIs."
    instruction += "\nProvide bodies only for the constructor; all six operation methods must remain stubbed."
    return JavaConversionOutput.model_validate_json(AdkExecutor(profile).execute(instruction, json.dumps(payload)))


def make_pass_generator(profile, payload, build_context, model_call=None):
    """Return a pass callback that rejects edits outside the requested method."""
    if model_call is None:
        if profile.model_provider == "mock":
            raise ValueError("Mock assembly requires explicit implementation fixtures")
        model_call = AdkExecutor(profile).execute
    def generate(implementation_pass, current_class, routing, context, serialization, compiler_error):
        instruction = re.sub(r"\{[A-Za-z_][A-Za-z0-9_]*\}", "See assembly input JSON", IMPLEMENTATION_PASS_INSTRUCTION)
        instruction += "\nReturn JSON with java_source and dependencies. Preserve the class outside the requested method exactly."
        request = dict(payload, method_name=implementation_pass.method_name, current_class=current_class,
                       routing_plan=routing.model_dump(mode="json"), context_plan=context.model_dump(mode="json"),
                       serialization_plan=serialization.model_dump(mode="json"), compiler_error=compiler_error)
        output = JavaConversionOutput.model_validate_json(model_call(instruction, json.dumps(request)))
        name = implementation_pass.method_name
        if extract_method(output.java_source, name) is None:
            raise ValueError("Implementation output is missing its requested method")
        before = replace_method_body(current_class, name, ["// method boundary"])
        after = replace_method_body(output.java_source, name, ["// method boundary"])
        if before != after:
            raise ValueError("Implementation pass modified code outside its requested method")
        merge_dependencies(build_context.pom_path, output.dependencies, build_context.verifier,
                           allowed_ibm_artifacts=build_context.allowed_ibm_artifacts,
                           task_id="assembly-" + name)
        return output.java_source
    return generate


def skeleton_path(build_context, operation_id: str, source: str) -> Path:
    """Require the operation's service class and a complete set of stub methods."""
    expected = operation_id + "Service"
    declaration = re.search(r"\bpublic\s+(?:final\s+)?class\s+(\w+)", source)
    if declaration is None or declaration.group(1) != expected:
        raise ValueError("Skeleton public class does not match the operation service")
    package = re.search(r"\bpackage\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*;", source)
    if package is None:
        raise ValueError("Skeleton must declare a valid Java package")
    for implementation_pass in PASSES:
        method = extract_method(source, implementation_pass.method_name)
        if method is None or "UnsupportedOperationException" not in method:
            raise ValueError("Skeleton must expose all six stubbed assembly methods")
    return build_context.source_root / Path(*package.group(1).split(".")) / (expected + ".java")
