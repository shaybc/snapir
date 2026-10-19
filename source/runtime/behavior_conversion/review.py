"""Review accepted native behavior with traceability before human gate decisions."""

from pydantic import BaseModel, ConfigDict, Field
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.review_payload import review_requests
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools.behavior_units import save


class BehaviorReview(BaseModel):
    """Model assessment is explicit evidence, not a substitute for human acceptance."""

    model_config = ConfigDict(extra="forbid")
    approved: bool
    issues: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)


def review_behavior(conn, config, profile, identity, payload, model_call=None):
    """Check configured rules, API/data flow and test assertions against original evidence."""
    instruction = "Review native behavior against exact original XML, source evidence, contracts, generated code and tests. Check transformations and decorator direction, configured values, side effects, return/error routing and contract compatibility. Do not demand preservation of Composer classes. Reject invented behavior, weak tests or missing requirements. Report concrete unresolved evidence. Return schema JSON; compilation alone does not prove equivalence."
    from runtime.behavior_conversion.response_json import JSON_INSTRUCTION
    from runtime.behavior_conversion.compatibility import versioned_requirements
    payload = dict(payload)
    requirements = versioned_requirements(profile, "review", payload)
    payload["versioned_requirements"] = requirements
    if requirements:
        payload["requirements"] = {item["requirement_id"]: item["description"] for item in requirements}
    requests = review_requests(payload, instruction + "\n" + JSON_INSTRUCTION,
                               BehaviorReview.model_json_schema(), profile.behavior_context_chars)
    if len(requests) == 1:
        return generate(conn, config, profile, "review", identity, instruction,
            requests[0], BehaviorReview, model_call=model_call, label="Behavior review: " + identity)
    results, fingerprints = [], []
    for index, request in enumerate(requests):
        result, fingerprint = generate(conn, config, profile, "review", identity + ":review-part:" + str(index + 1),
            instruction, request, BehaviorReview, model_call=model_call,
            label=f"Behavior review {index + 1}/{len(requests)}: " + identity)
        results.append(result)
        fingerprints.append(fingerprint)
    issues = list(dict.fromkeys(issue for result in results for issue in result.issues))
    questions = list(dict.fromkeys(question for result in results for question in result.unresolved_questions))
    result = BehaviorReview(approved=all(item.approved for item in results) and not issues and not questions,
                            issues=issues, unresolved_questions=questions)
    fingerprint = stable_id(fingerprints, "review-parts-v1")
    save(conn, config.run_id, "review", identity, fingerprint, result.model_dump(mode="json"))
    return result, fingerprint
