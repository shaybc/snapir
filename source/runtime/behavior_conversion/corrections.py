"""Route final validation feedback to accepted native owners with durable budgets."""

import json
from tools.state_store_tools.behavior_units import snapshot, save
from tools.component_inventory_tools.identity import stable_id


def route_native_correction(conn, config, item, result):
    """Never route a native operation through legacy assembly/component state."""
    category = result.get("failure_class")
    if category == "validation_fixture_gap" or (result.get("build_passed") and result.get("package_passed")
                                                and result.get("test_status") == "not_available"):
        return "evidence"
    if category in {None, "build_failure", "equivalence_gap"}:
        return "generation"
    consumer = item["channel"] + "/" + item["operation_id"]
    if category == "routing_mismatch":
        owners, route = [("service", consumer)], "assembly"
    elif category in {"conversion_gap", "shared_component_gap"}:
        owned = {binding["unit_id"] for binding in item["payload"]["bindings"].values()}
        requested = result.get("native_unit_ids", [])
        if not requested or not isinstance(requested, list) or not set(requested).issubset(owned):
            return "human"
        owners, route = [("unit", identity) for identity in sorted(set(requested))], "component"
    else:
        return "human"
    for category, identity in owners:
        prior = snapshot(conn, config.run_id, "correction", category + ":" + identity)
        if prior and json.loads(prior["data_json"])["attempts"] >= config.max_agent_task_retries:
            return "exhausted"
    for category, identity in owners:
        prior = snapshot(conn, config.run_id, "correction", category + ":" + identity)
        attempts = json.loads(prior["data_json"])["attempts"] if prior else 0
        data = dict(attempts=attempts + 1, validation_feedback=result.get("findings") or [json.dumps(result, sort_keys=True)])
        save(conn, config.run_id, "correction", category + ":" + identity, stable_id(data), data)
    return route


def correction_feedback(conn, run_id, category, identity):
    """Return persisted owner-specific feedback as part of the next input identity."""
    prior = snapshot(conn, run_id, "correction", category + ":" + identity)
    return json.loads(prior["data_json"]) if prior else None
