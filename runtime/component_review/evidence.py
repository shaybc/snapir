"""Collect exact conversion inputs and content fingerprints for component review."""

import hashlib
import json
from pathlib import Path

from tools.state_store_tools._json import loads


def collect_component_evidence(conn, config, profile):
    """Return expected task evidence; missing or uncompiled components stay blocking."""
    rows = conn.execute("SELECT * FROM agent_tasks WHERE run_id=? AND agent_name='ManagedConversion' ORDER BY task_id",
                        (config.run_id,)).fetchall()
    evidence = []
    for task in rows:
        data = loads(task["input_json"], {}) or {}
        artifact_id = f"{config.run_id}:native_java:{task['task_id']}"
        artifact = conn.execute("SELECT * FROM native_java_artifacts WHERE run_id=? AND artifact_id=?",
                                (config.run_id, artifact_id)).fetchone()
        owner = data.get("managed_project_operation")
        from runtime.shared_libraries.ownership import component_project
        project = component_project(config, data, task["channel"])
        item = dict(task_id=task["task_id"], artifact_id=artifact_id, conversion_id=data.get("conversion_id", task["scope_id"]),
                    kind=data.get("kind"), original_source=data.get("primary_source_content", ""),
                    task_input=data, project=str(project.resolve()), source_path=None, issues=[])
        if not item["original_source"]:
            item["issues"].append("Exact conversion input is missing")
        if artifact is None:
            item["issues"].append("Expected converted artifact is missing")
        elif not artifact["compiles"] or artifact["status"] not in {"converted", "validated"} or task["status"] not in {"completed", "validated"}:
            item["issues"].append("Component is not successfully compiled or has been invalidated")
        try:
            if artifact is None or not artifact["artifact_path"]:
                raise ValueError("Converted source path is missing")
            path = Path(artifact["artifact_path"]).resolve()
            if not path.is_relative_to(project.resolve() / "src/main/java"):
                raise ValueError("Converted component is outside its managed project")
            item["source_path"] = str(path)
            item["converted_source"] = path.read_text(encoding="utf-8")
            pom = project / "pom.xml"
            item["pom_hash"] = hashlib.sha256(pom.read_bytes()).hexdigest()
            item["source_hash"] = hashlib.sha256(path.read_bytes()).hexdigest()
        except (ValueError, OSError) as exc:
            item["issues"].append(str(exc))
            item.setdefault("converted_source", "")
            item.setdefault("pom_hash", "missing")
            item.setdefault("source_hash", "missing")
        if not item["converted_source"].strip():
            item["issues"].append("Converted Java source is empty")
        if data.get("dependency_component_keys"):
            from runtime.shared_libraries.dependencies import dependency_binding, converted_dependency_apis
            try:
                current = dependency_binding(conn, config, data.get("source_component_key"))
                if current.get("dependency_source_hash") != data.get("dependency_source_hash"):
                    raise ValueError("Original utility dependencies changed since conversion")
                if converted_dependency_apis(conn, config, data) != data.get("converted_dependency_apis"):
                    raise ValueError("Native utility APIs changed since caller conversion")
            except (ValueError, OSError) as exc:
                item["issues"].append(str(exc))
        fingerprint = dict(input=data, source_hash=item["source_hash"], pom_hash=item["pom_hash"],
                           review_contract_version="1",
                           model=profile.model_name, model_provider=profile.model_provider,
                           ibm_classes=profile.allowed_ibm_classes, ibm_artifacts=profile.allowed_ibm_artifacts,
                           repositories=profile.approved_maven_repository_urls)
        item["fingerprint"] = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
        evidence.append(item)
    return evidence
