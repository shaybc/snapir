"""Protect accepted files while rebuilding only affected operation test scenarios."""

import json
from runtime.behavior_conversion.bundle_output import verify_manifest
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools.behavior_units import snapshot, save


def validate_child(conn, config, identity, child_identity, bundle, cached, validator):
    """Advance the parent manifest only after a protected child build succeeds."""
    parent_identity = "service:" + identity
    prior = snapshot(conn, config.run_id, "manifest", parent_identity)
    parent = json.loads(prior["data_json"]) if prior else None
    if parent:
        verify_manifest(parent["project"], parent["files"])
    old = snapshot(conn, config.run_id, "manifest", child_identity)
    previous_files = json.loads(old["data_json"])["files"] if old else {}
    validator(bundle, cached=cached)
    if cached:
        return
    child = json.loads(snapshot(conn, config.run_id, "manifest", child_identity)["data_json"])
    files = dict(parent["files"] if parent else {})
    for name in set(previous_files) - set(child["files"]):
        files.pop(name, None)
    files.update(child["files"])
    save(conn, config.run_id, "manifest", parent_identity, stable_id(files),
        dict(project=child["project"], files=files, validation={}), "provisional")


def stale_scenario_files(conn, config, identity, plan, source_revision):
    """Identify app-owned stale tests without deleting their canonical files."""
    current = {identity + ":" + scenario.scenario_id: scenario.model_dump() for scenario in plan.scenarios}
    files, removed = {}, []
    prefix = "route_scenario:" + identity + ":"
    rows = conn.execute("SELECT identity,data_json FROM behavior_snapshots WHERE run_id=? AND category='manifest' AND status='accepted'",
        (config.run_id,)).fetchall()
    for row in rows:
        if not row["identity"].startswith(prefix):
            continue
        scenario_identity = row["identity"].removeprefix("route_scenario:")
        data = json.loads(row["data_json"])
        previous = conn.execute("SELECT request_json FROM behavior_attempts WHERE run_id=? AND category='route_scenario_test' AND identity=? AND error IS NULL AND response IS NOT NULL ORDER BY created_at DESC LIMIT 1",
            (config.run_id, scenario_identity)).fetchone()
        request = json.loads(previous["request_json"]) if previous else {}
        if request.get("source_revision") == source_revision and request.get("scenario") == current.get(scenario_identity):
            continue
        verify_manifest(data["project"], data["files"])
        files.update(data["files"])
        if scenario_identity not in current:
            removed.append((scenario_identity, row["identity"], data))
    return files, removed


def retire_removed_scenarios(conn, config, removed):
    """Retain history but stop reusing removed scenario files after final acceptance."""
    for identity, manifest_identity, data in removed:
        prior = snapshot(conn, config.run_id, "route_scenario_test", identity)
        if prior:
            save(conn, config.run_id, "route_scenario_test", identity, prior["fingerprint"], json.loads(prior["data_json"]), "retired")
        save(conn, config.run_id, "manifest", manifest_identity, stable_id(data),
            dict(data, retired_files=data["files"], files={}), "retired")
