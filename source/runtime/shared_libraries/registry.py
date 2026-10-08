"""Register approved conversions and reject stale source, output or build evidence."""

import hashlib
import json
from pathlib import Path

from models.registry_models import ComponentRegistryRecord
from tools.artifact_registry_tools.component_registry import register_component
from tools.artifact_registry_tools.reuse_resolver import resolve_component_reuse
from tools.component_inventory_tools.identity import stable_id


def conversion_hash(data, profile):
    """Fingerprint conversion inputs and relevant policy independently of consumer ordering."""
    return stable_id(data["kind"], data["primary_source_content"], data.get("source_component_hash"),
                     data.get("dependency_source_hash"), data.get("converted_dependency_apis"),
                     data.get("managed_library_id"),
                     *([data["external_dependencies"]] if data.get("external_dependencies") else []),
                     data.get("composer_behavior_evidence", []),
                     data.get("relationship_context") if data.get("managed_project_operation") else None,
                     profile.model_name, profile.model_provider, profile.model_base_url,
                     profile.model_timeout_seconds, profile.max_model_attempts,
                     profile.maven_settings_path, profile.maven_local_repository,
                     profile.allowed_ibm_artifacts, profile.allowed_ibm_classes,
                     profile.approved_maven_repository_urls, getattr(profile, "java_version", "25"),
                     getattr(profile, "java_home", None), "managed-class-v1")


def register_approved_components(conn, config, profile, evidence):
    """Publish component-level compiled/reviewed results after accepted Gate 2 only."""
    for item in evidence:
        data = item["task_input"]
        key = data.get("source_component_key")
        if not key:
            continue
        digest = conversion_hash(data, profile)
        component_id = "managed-component-" + stable_id(config.run_id, key, digest)
        record = dict(source_key=key, input_hash=digest, output_hash=item["source_hash"],
                      pom_hash=item["pom_hash"], source_path=item["source_path"], project=item["project"],
                      library_id=data.get("managed_library_id"), java_source=item["converted_source"])
        register_component(conn, ComponentRegistryRecord(component_id=component_id, artifact_kind="managed_native",
            logical_id=key, source_path=data.get("source_origin", ""), source_hash=digest, target_language="java",
            artifact_schema_version="v1", generated_path=item["source_path"], status="validated",
            used_by_operations=data.get("consumer_operations", []), used_by_validated_operations=0))
        conn.execute("INSERT OR REPLACE INTO managed_component_registry VALUES (?, ?, ?, ?, ?)",
                     (component_id, key, digest, item["task_id"], json.dumps(record)))
    conn.commit()


def reusable_component(conn, config, profile, data, context):
    """Return a current reviewed artifact from this run-owned registry, or no reuse."""
    key = data.get("source_component_key")
    if not key or data.get("component_review_feedback"):
        return None
    digest = conversion_hash(data, profile)
    decision = resolve_component_reuse(conn, "managed_native", key, digest, data["channel"], "java")
    if not decision.should_reuse:
        return None
    row = conn.execute("SELECT record_json FROM managed_component_registry WHERE component_id=? AND input_hash=?",
                       (decision.component_id, digest)).fetchone()
    if not row:
        return None
    record = json.loads(row[0])
    path = Path(record["source_path"])
    try:
        if not path.resolve().is_relative_to(context.source_root.resolve()):
            return None
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["output_hash"]:
            return None
        if hashlib.sha256(Path(context.pom_path).read_bytes()).hexdigest() != record["pom_hash"]:
            return None
    except OSError:
        return None
    return record
