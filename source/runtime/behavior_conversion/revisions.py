"""Bound review-driven bundle corrections and retain them across Resume."""

import json
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.review import review_behavior
from runtime.behavior_conversion.compatibility import versioned_requirements
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools.behavior_units import snapshot, save
from tools.state_store_tools.agent_tasks import upsert_agent_task


def generate_reviewed_bundle(conn, config, profile, category, identity, instruction, payload,
                             validator, review_payload, model_call=None, label="", bundle_generator=None):
    """Review code against original evidence; retry concrete defects, preserve unknowns."""
    revision_hash = stable_id(payload, versioned_requirements(profile, category, payload),
                              profile.java_version, profile.java_home)
    prior = snapshot(conn, config.run_id, "revision", category + ":" + identity)
    revision = json.loads(prior["data_json"]) if prior and prior["fingerprint"] == revision_hash else {"number": 0}
    while True:
        request = dict(payload)
        if revision["number"]:
            request.update(behavior_review_feedback=revision["feedback"], previous_bundle=revision["bundle"])
        if bundle_generator is None:
            bundle, fingerprint = generate(conn, config, profile, category, identity, instruction, request,
                NativeUnitBundle, validator, model_call, label)
        else:
            def record(status, output=None, error=None, fingerprint=None):
                upsert_agent_task(conn, run_id=config.run_id, agent_name="BehaviorConversion",
                    scope_type=category, scope_id=identity, channel="", target_language="java",
                    status=status, attempt_number=revision["number"], max_retries=profile.max_agent_task_retries,
                    input_data={"fingerprint": fingerprint or revision_hash, "phase": "incremental_operation"},
                    output_data=output, error_message=error)
            record("started")
            try:
                bundle, fingerprint = bundle_generator(request)
            except Exception as exc:
                record("failed", error=str(exc))
                raise
            record("completed", output=bundle.model_dump(mode="json"), fingerprint=fingerprint)
        review, review_hash = review_behavior(conn, config, profile, identity,
            review_payload(bundle), model_call)
        if (review.approved and not review.issues and not review.unresolved_questions) or review.unresolved_questions:
            return bundle, fingerprint, review, review_hash
        if revision["number"] >= profile.max_agent_task_retries:
            return bundle, fingerprint, review, review_hash
        revision = dict(number=revision["number"] + 1, feedback=review.model_dump(mode="json"),
                        bundle=bundle.model_dump(mode="json"))
        save(conn, config.run_id, "revision", category + ":" + identity, revision_hash, revision)
