"""Route explicit validation failures with durable, channel-scoped correction budgets."""

import json
from pathlib import Path

from tools.state_store_tools._json import loads, utc_now


def route_correction(conn, config, item, result):
    """Queue a known upstream owner or return generation, evidence, human, or exhausted."""
    category = result.get("failure_class")
    if category == "validation_fixture_gap" or (result.get("build_passed") and
            result.get("package_passed") and result.get("test_status") == "not_available"):
        return "evidence"
    if category not in {None, "build_failure", "equivalence_gap", "conversion_gap",
                        "shared_component_gap", "routing_mismatch"}:
        return "human"
    target = "assembly" if category == "routing_mismatch" else "component" if category in {
        "conversion_gap", "shared_component_gap"} else "generation"
    if target == "generation":
        return target
    owners = []
    if target == "component":
        requested = result.get("component_task_ids", [])
        if not requested or not isinstance(requested, list):
            return "human"
        for task_id in set(requested):
            row = conn.execute("SELECT * FROM agent_tasks WHERE task_id=? AND run_id=? AND agent_name='ManagedConversion'",
                               (task_id, config.run_id)).fetchone()
            data = loads(row["input_json"], {}) if row else {}
            owner = data.get("managed_project_operation")
            if row is None or (owner is not None and (owner != item["operation_id"] or row["channel"] != item["channel"])):
                return "human"
            if owner is None and category != "shared_component_gap":
                return "human"
            if data.get("consumer_operations") is not None and item["channel"] + "/" + item["operation_id"] not in data["consumer_operations"]:
                return "human"
            owners.append((row, data))
    conn.execute("""CREATE TABLE IF NOT EXISTS service_correction_attempts (
        run_id TEXT, operation_id TEXT, channel TEXT, attempts INTEGER NOT NULL,
        PRIMARY KEY(run_id,operation_id,channel))""")
    key = (config.run_id, item["operation_id"], item["channel"])
    row = conn.execute("SELECT attempts FROM service_correction_attempts WHERE run_id=? AND operation_id=? AND channel=?", key).fetchone()
    count = row[0] if row else 0
    if count >= config.max_agent_task_retries:
        return "exhausted"
    feedback = result.get("findings") or [json.dumps(result, sort_keys=True)]
    if target == "assembly":
        conn.execute("UPDATE agent_tasks SET status='needs_rerun',output_json=?,updated_at=? WHERE task_id=? AND run_id=? AND channel=?",
                     (json.dumps(dict(equivalence_feedback=feedback)), utc_now(), item["assembly_task_id"], config.run_id, item["channel"]))
        conn.execute("DELETE FROM operation_assembly_snapshots WHERE run_id=? AND operation_id=? AND channel=?", key)
    else:
        for task, data in owners:
            artifact = conn.execute("SELECT artifact_path FROM native_java_artifacts WHERE run_id=? AND artifact_id=?",
                                    (config.run_id, f"{config.run_id}:native_java:{task['task_id']}")).fetchone()
            data["component_review_feedback"] = feedback
            if artifact and Path(artifact[0]).is_file():
                data["previous_converted_source"] = Path(artifact[0]).read_text(encoding="utf-8")
            conn.execute("UPDATE agent_tasks SET status='pending',input_json=?,updated_at=? WHERE task_id=?",
                         (json.dumps(data), utc_now(), task["task_id"]))
        # Shared components can affect every operation; all assemblies must be rebuilt.
        if category == "shared_component_gap":
            conn.execute("DELETE FROM operation_assembly_snapshots WHERE run_id=?", (config.run_id,))
        else:
            conn.execute("DELETE FROM operation_assembly_snapshots WHERE run_id=? AND operation_id=? AND channel=?", key)
    conn.execute("INSERT OR REPLACE INTO service_correction_attempts VALUES (?, ?, ?, ?)", (*key, count + 1))
    conn.commit()
    return target
