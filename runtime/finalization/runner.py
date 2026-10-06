"""Render deployment deliverables and bind Gate 4 to complete validation evidence."""

import hashlib
import json
from pathlib import Path

from agents.documentation_report.agent import generate_operation_doc
from agents.java_deployment_manifest.agent import build_deployment_spec
from runtime.human_gates import evaluate_gate
from runtime.operation_review.evidence import collect_operation_evidence
from runtime.service_generation.runner import _project_hash
from tools.deployment_tools.template_renderer import render_manifest
from tools.state_store_tools.generated_artifacts import upsert_generated_artifact
from tools.state_store_tools.runs import update_run_status


def run_finalization(conn, config, profile, plan, directory):
    """Write manifest/docs inventories and require evidence-complete approval at Gate 4."""
    directory = Path(directory)
    evidence = collect_operation_evidence(conn, config, profile, plan)
    blockers = []
    deliverables = []
    report3 = (directory / "gate_3_report.txt").read_text(encoding="utf-8")
    if evaluate_gate(conn, config.run_id, 3, report3, "human", True) != "approved":
        blockers.append("Current Gate 3 is not approved")
    for item in evidence:
        key = (config.run_id, item["operation_id"], item["channel"])
        label = item["channel"] + "/" + item["operation_id"]
        project = directory / "services" / item["channel"] / item["operation_id"]
        output = directory / "deliverables" / item["channel"] / item["operation_id"]
        output.mkdir(parents=True, exist_ok=True)
        issues = list(item["issues"])
        validation = {}
        evidence_files = []
        try:
            row = conn.execute("SELECT * FROM service_generation_checkpoints WHERE run_id=? AND operation_id=? AND channel=?", key).fetchone()
            expected = hashlib.sha256((item["fingerprint"] + report3).encode()).hexdigest()
            if row is None or row["input_hash"] != expected or not row["project_hash"] or _project_hash(project) != row["project_hash"]:
                raise ValueError("Generated project evidence is missing or stale")
            validation = json.loads(row["validation_json"])
            for name in ("build_passed", "package_passed", "ibm_guard_passed"):
                if validation.get(name) is not True:
                    issues.append(name + " has not passed")
            for name in ("test_status", "xml_compatibility", "behavioral_equivalence", "legacy_trace_comparison"):
                if validation.get(name) != "passed":
                    issues.append(name + " evidence is unavailable or failed")
            for name in ("xml_compatibility", "behavioral_equivalence", "legacy_trace_comparison"):
                paths = validation.get("evidence_paths", {}).get(name, [])
                if not paths:
                    issues.append(name + " supporting evidence files are missing")
                for value in paths:
                    path = (directory / value).resolve()
                    if not path.is_relative_to(directory.resolve()) or not path.is_file():
                        issues.append(name + " evidence file is unavailable or outside the run")
                    else:
                        evidence_files.append(path)
            values = profile.deployment_values.get(label)
            if not profile.deployment_template_dir or not values or not values.get("image_name"):
                raise ValueError("Deployment templates and explicit image configuration are required")
            spec = build_deployment_spec(item["operation_id"], values, template_dir=profile.deployment_template_dir)
            manifest = render_manifest(profile.deployment_template_dir, spec)
            manifest_root = output / "deployment"
            manifest_root.mkdir(exist_ok=True)
            for filename, content in manifest.files.items():
                path = manifest_root / filename
                if Path(filename).name != filename or ":" in filename:
                    raise ValueError("Unsafe deployment template filename")
                path.write_text(content, encoding="utf-8")
            upsert_generated_artifact(conn, artifact_id="final-manifest-" + hashlib.sha256(":".join(key).encode()).hexdigest(),
                run_id=config.run_id, operation_id=item["operation_id"], channel=item["channel"], target_language="java",
                artifact_kind="deployment_manifest", generated_path=str(manifest_root), status="converted",
                blocking_reason=None, attempt_number=1)
        except Exception as exc:
            issues.append(str(exc))
        document = generate_operation_doc(operation_id=item["operation_id"], channel=item["channel"],
            operation_xml=item.get("original_xml", ""), service_path=str(project),
            routing_plan_summary=json.dumps(item["routing"].model_dump(mode="json")) if "routing" in item else "unavailable",
            validation_report=dict(build_passed=validation.get("build_passed"), test_passed=validation.get("test_status") == "passed",
                xml_compat_passed=validation.get("xml_compatibility") == "passed", ibm_guard_passed=validation.get("ibm_guard_passed"),
                behavior_equiv_passed=validation.get("behavioral_equivalence") == "passed"),
            shared_components=[], generated_files=[str(path.relative_to(directory)) for path in sorted(project.rglob("*")) if path.is_file()])
        document = document.replace(f"{item['operation_id']} was migrated for channel {item['channel']}.",
                                    f"Generated candidate for channel {item['channel']}; production readiness requires Gate 4.")
        document += "\n## Evidence and blockers\n" + json.dumps(dict(validation=validation, blockers=issues), indent=2) + "\n"
        (output / "README.md").write_text(document, encoding="utf-8")
        blockers.extend(label + ": " + issue for issue in issues)
        files = [*sorted(project.rglob("*")), *sorted(output.rglob("*")), *evidence_files]
        deliverables.append(dict(operation_id=item["operation_id"], channel=item["channel"], blockers=issues,
            files={str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in files if path.is_file() and path.suffix not in {".lock"}}))
    inventory = dict(run_id=config.run_id, operations=deliverables, blockers=blockers,
                     deployed=False, production_ready=bool(evidence) and not blockers)
    (directory / "delivery_manifest.json").write_text(json.dumps(inventory, sort_keys=True, indent=2), encoding="utf-8")
    final_report = "# Migration deliverable review\n\nNo cluster deployment or image publication was performed.\n\n" + json.dumps(inventory, sort_keys=True, indent=2)
    (directory / "final_report.md").write_text(final_report, encoding="utf-8")
    report = "=== Human Gate 4 ===\nProduction readiness review; approval does not deploy anything.\n" + final_report
    (directory / "gate_4_report.txt").write_text(report, encoding="utf-8")
    decision = evaluate_gate(conn, config.run_id, 4, report, profile.gate_policies.get("4", "human"), bool(evidence) and not blockers)
    phase = "migration_approved" if decision == "approved" else "finalization_blocked" if decision == "blocked" else "gate_4_" + decision
    update_run_status(conn, config.run_id, "completed" if decision == "approved" else "blocked" if decision == "blocked" else
                      "stopped" if decision == "rejected" else "paused", phase)
    return phase
