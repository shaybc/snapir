"""Combine deterministic checks and model review of exact conversion snapshots."""

import json
import re

from agents.source_conversion.native_java_reviewer.agent import (
    NATIVE_JAVA_REVIEW_INSTRUCTION, parse_review_output, review_native_java,
)
from models.conversion_models import ConversionReviewResult
from runtime.model_execution.adk_executor import AdkExecutor
from tools.validation_tools.ibm_dependency_guard_tool import scan_source
from constants import FORBIDDEN_DEPENDENCIES


def review_component(item, profile, model_reviewer=None) -> ConversionReviewResult:
    """Require both structural checks and an explicit model review result."""
    kind = {"xml_fmtdef": "xml_fmtdef_dto", "xml_context": "context_class"}.get(item["kind"], "ibm_java")
    deterministic = review_native_java(item["original_source"], item["converted_source"], review_kind=kind,
                                       allowed_ibm_classes=profile.allowed_ibm_classes)
    issues = list(deterministic.issues)
    issues.extend("Prohibited dependency remains: " + finding for finding in
                  scan_source(item["converted_source"], FORBIDDEN_DEPENDENCIES, allowed_classes=profile.allowed_ibm_classes))
    if "TODO" in item["converted_source"]:
        return ConversionReviewResult(conversion_id=item["conversion_id"], issues=[*issues, "Unresolved TODO in converted source"],
                                      confidence="low", review_status="needs_human_review")
    if kind == "context_class":
        try:
            fields = json.loads(item["original_source"])
            for field in fields:
                name = field["name"]
                accessor = name[:1].upper() + name[1:]
                for method in ("get" + accessor, "set" + accessor):
                    if not re.search(r"\b" + re.escape(method) + r"\s*\(", item["converted_source"]):
                        issues.append("Context accessor missing: " + method)
        except (TypeError, ValueError, KeyError):
            issues.append("Context field inventory cannot be verified")
    if model_reviewer is None:
        if profile.model_provider == "mock":
            raise ValueError("Component review in mock mode requires an explicit review fixture")
        instruction = re.sub(r"\{[A-Za-z_][A-Za-z0-9_]*\}", "See review input JSON", NATIVE_JAVA_REVIEW_INSTRUCTION)
        instruction += "\nExact approved IBM client imports: " + json.dumps(profile.allowed_ibm_classes)
        instruction += "\nListed approved client imports are permitted; Composer runtime dependencies are never permitted."
        output = AdkExecutor(profile).execute(instruction, json.dumps(dict(
            review_kind=kind, original_source=item["original_source"], converted_java=item["converted_source"],
            conversion_requirements=item["task_input"], pom_hash=item["pom_hash"])))
        result = parse_review_output(item["conversion_id"], output)
    else:
        result = model_reviewer(item)
        result = ConversionReviewResult.model_validate(result)
    if result.review_status not in {"approved", "needs_revision", "needs_human_review"}:
        raise ValueError("Component reviewer returned an unsupported decision")
    issues = list(dict.fromkeys([*issues, *result.issues]))
    status = result.review_status
    if result.confidence == "low":
        status = "needs_human_review"
    elif issues and status == "approved":
        status = "needs_revision"
    return result.model_copy(update=dict(conversion_id=item["conversion_id"], issues=issues, review_status=status))
