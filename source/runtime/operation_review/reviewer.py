"""Combine structural review with explicit XML-to-service model comparison."""

import json
import re

from constants import FORBIDDEN_DEPENDENCIES
from agents.operation_assembly.operation_equivalence_reviewer.agent import EQUIVALENCE_REVIEW_INSTRUCTION, review_operation_equivalence
from models.conversion_models import EquivalenceReviewResult
from runtime.model_execution.adk_executor import AdkExecutor
from tools.validation_tools.ibm_dependency_guard_tool import scan_source


def review_assembled_operation(item, profile, model_reviewer=None):
    """Require structural correctness and a high/medium-confidence model decision."""
    deterministic = review_operation_equivalence(item["java_source"], item["routing"], item["context"], item["serialization"],
                            forbidden=[pattern for pattern in FORBIDDEN_DEPENDENCIES if pattern != "com.ibm"],
                            expected_return_type=item["expected_return_type"])
    forbidden = scan_source(item["java_source"], FORBIDDEN_DEPENDENCIES, allowed_classes=profile.allowed_ibm_classes)
    if model_reviewer is None:
        if profile.model_provider == "mock":
            raise ValueError("Mock operation review requires explicit review fixtures")
        instruction = re.sub(r"\{[A-Za-z_][A-Za-z0-9_]*\}", "See operation-review input JSON", EQUIVALENCE_REVIEW_INSTRUCTION)
        instruction += "\nReturn JSON matching the supplied EquivalenceReviewResult schema."
        instruction += "\nCompare behavior with the original XML and approved component APIs, not merely with the plans."
        instruction += "\nUse the actual expected_return_type when supplied. Exact approved IBM client imports are allowed; legacy runtime imports are never allowed."
        response = AdkExecutor(profile).execute(instruction, json.dumps(dict(item["payload"], schema=EquivalenceReviewResult.model_json_schema())))
        result = EquivalenceReviewResult.model_validate_json(response)
    else:
        result = EquivalenceReviewResult.model_validate(model_reviewer(item))
    if result.operation_id != item["operation_id"] or result.review_status not in {"approved", "needs_revision", "needs_human_review"}:
        raise ValueError("Operation reviewer returned an invalid owner or decision")
    updates = {key: list(dict.fromkeys([*getattr(deterministic, key), *getattr(result, key)])) for key in
               ("missing_steps", "missing_rc_branches", "context_mutation_issues", "logic_differences")}
    updates["logic_differences"] += ["Prohibited dependency remains: " + value for value in forbidden]
    issues = [value for values in updates.values() for value in values]
    updates["review_status"] = "needs_human_review" if result.confidence == "low" else "needs_revision" if issues and result.review_status == "approved" else result.review_status
    return result.model_copy(update=updates)
