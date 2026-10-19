"""Project saved evidence into the active stage's console progress tree."""

import json
import sqlite3

from runtime.workflow_stages import workflow_stage
from runtime.workflow_subsections import SUBSECTIONS
from runtime.workspace_paths import run_report_path


def _rows(conn, table, run_id):
    """Read optional state tables without creating or migrating a saved database."""
    try:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(f"SELECT * FROM {table} WHERE run_id=?", (run_id,))]
    except sqlite3.Error:
        return []


def _json(value):
    try:
        return json.loads(value or "{}")
    except (ValueError, TypeError):
        return {}


def _report(directory, name):
    try:
        return _json(run_report_path(directory, name).read_text(encoding="utf-8"))
    except OSError:
        return {}


def _task_status(value):
    if value in {"completed", "accepted", "approved", "converted"}:
        return "completed"
    if value in {"failed", "blocked", "stopped", "needs_revision", "needs_human_review", "needs_rerun"}:
        return "attention"
    return "current" if value in {"started", "in_progress"} else "pending"


def _aggregate(values):
    if "attention" in values:
        return "attention"
    if "current" in values:
        return "current"
    return "completed" if values and all(value == "completed" for value in values) else "pending"


def _failure_step(error, request):
    """Locate a rejection using structured diagnostics before falling back to its reason."""
    compiler = request.get("failed_compiler_context")
    tests = request.get("failed_test_context")
    text = (error or "").lower()
    if tests or "maven test" in text or "failed behavioral tests" in text:
        return "test"
    if compiler or "maven compile" in text:
        return "compile"
    if any(word in text for word in ("interface", "contract", "metadata", "method")):
        return "interfaces"
    if any(word in text for word in ("dependenc", "jar", "artifact", "version conflict")):
        return "dependencies"
    return "json"


def _assembly(states, extra, snapshots, attempts, tasks, phase):
    implementations = [row for row in attempts if row["category"] == "service_implementation"]
    accepted = {(row["category"], row["identity"]): row for row in snapshots if row["status"] == "accepted"}
    if implementations:
        for key in ("gather", "gather.units", "gather.routing"):
            states[key] = "completed"
        latest = max(implementations, key=lambda row: row["created_at"])
        output = _json(latest.get("response"))
        request = _json(latest["request_json"])
        if latest.get("response"):
            states["generate.service"] = states["generate"] = "completed"
            failed = _failure_step(latest.get("error"), request)
            states["validate.json"] = "completed" if output.get("files") and failed != "json" else "pending"
            if latest.get("error"):
                if failed in {"compile", "test", "dependencies"}:
                    states["validate.interfaces"] = "completed"
                states["validate." + failed] = "attention"
                states["validate"] = "attention"
                extra.setdefault("validate", []).append(("detail", latest["identity"] + ": " + latest["error"].splitlines()[0], "attention", []))
            elif ("service_implementation", latest["identity"]) not in accepted:
                states["validate"] = "current"
        else:
            states["generate.service"] = states["generate"] = "attention" if latest.get("error") else "current"
    if implementations and not latest.get("error") and ("service_implementation", latest["identity"]) in accepted:
        for key in ("generate", "generate.service", "validate", "validate.json", "validate.interfaces", "validate.compile"):
            states[key] = "completed"
    plans = [row for row in snapshots if row["category"] == "route_test_plan"]
    for row in plans:
        states["plan"] = _task_status(row["status"])
        states["plan.generate"] = "completed" if row["status"] == "accepted" else states["plan"]
        states["plan.coverage"] = states["plan"]
        history = [item for item in attempts if item["category"] == "route_test_plan" and item["identity"] == row["identity"]]
        if history and row["status"] != "accepted":
            latest = max(history, key=lambda item: item["created_at"])
            if _json(latest.get("response")).get("scenarios"):
                states["plan.generate"] = "completed"
        plan = _json(row["data_json"])
        for number, scenario in enumerate(plan.get("scenarios", []), 1):
            identity = row["identity"] + ":" + scenario["scenario_id"]
            history = [item for item in attempts if item["category"] == "route_scenario_test" and item["identity"] == identity]
            saved = accepted.get(("route_scenario_test", identity))
            status = "completed" if saved else "pending"
            children = [("generate", "Generate test", "pending", []), ("validate", "Validate", "pending", []),
                        ("compile", "Compile", "pending", []), ("test", "Run test", "pending", [])]
            if history:
                latest = max(history, key=lambda item: item["created_at"])
                if saved:
                    children = [(key, title, "completed", []) for key, title, _, _ in children]
                else:
                    status = "attention" if latest.get("error") else "current"
                    failed = _failure_step(latest.get("error"), _json(latest["request_json"]))
                    failed = failed if failed in {"compile", "test"} else "validate"
                    position = [item[0] for item in children].index(failed if latest.get("response") else "generate")
                    children = [(key, title, "completed" if index < position else status if index == position else "pending", [])
                                for index, (key, title, _, _) in enumerate(children)]
            extra.setdefault("scenarios", []).append((identity, f"{number}. {scenario['description']}", status, children))
    if extra.get("scenarios"):
        states["scenarios"] = _aggregate([item[2] for item in extra["scenarios"]])
    if any(key[0] == "service" for key in accepted) and states.get("validate") == "completed" and states.get("scenarios") == "completed":
        states["suite"] = "completed"
    service_tasks = [row for row in tasks if row.get("scope_type") == "service"]
    if service_tasks and states.get("scenarios") == "completed" and states.get("suite") != "completed":
        states["suite"] = _task_status(max(service_tasks, key=lambda row: row["updated_at"])["status"])
    reviews = [row for row in snapshots if row["category"] == "review" and "/" in row["identity"]]
    if reviews:
        states["review.behavior"] = _aggregate([_task_status(row["status"]) for row in reviews])
        for row in reviews:
            result = _json(row["data_json"])
            if result.get("issues") or result.get("unresolved_questions") or not result.get("approved"):
                states["review.behavior"] = "attention"


def active_subsections(conn, directory, status, phase):
    """Return only the active stage tree; completed marks require saved evidence."""
    stage = workflow_stage(phase)
    states, extra = {}, {}
    snapshots = _rows(conn, "behavior_snapshots", directory.name)
    attempts = _rows(conn, "behavior_attempts", directory.name)
    tasks = _rows(conn, "agent_tasks", directory.name)
    def done(key, condition):
        if condition:
            states[key] = "completed"
    if stage == "intake_and_legacy_analysis":
        for key, report in (("discover.sources", "java_source_index.json"), ("discover.classpath", "java_classpath_index.json"),
                            ("inventory.definitions", "component_inventory.json"), ("inventory.usage", "configured_component_usage.json")):
            done(key, bool(_report(directory, report)))
        done("mapper", bool(_rows(conn, "source_artifacts", directory.name)))
        analysis = [row for row in tasks if row.get("agent_name") == "LegacyComposerAnalysis"]
        if analysis:
            states["analysis"] = _aggregate([_task_status(row["status"]) for row in analysis])
        done("contexts.hierarchies", bool(_rows(conn, "context_hierarchies", directory.name)))
        done("contexts.scope", bool(_report(directory, "planning_inputs.json")))
    elif stage == "migration_planning":
        done("scope", bool(_report(directory, "planning_inputs.json")))
        planned = bool(_rows(conn, "migration_plans", directory.name))
        for key in ("plan", "plan.generate", "plan.validate"):
            done(key, planned)
        done("ownership", bool(_rows(conn, "shared_library_plans", directory.name)) or any(row["category"] == "ownership" for row in snapshots)
             or (directory / "reports/2_migration_planning/gate_1/shared_libraries.md").is_file())
        done("report", run_report_path(directory, "gate_1_report.md").is_file() or run_report_path(directory, "gate_1_report.txt").is_file())
    elif stage == "dependency_closure_and_component_conversion":
        closures = _report(directory, "dependency_closure.json")
        ready = bool(closures) and isinstance(closures, list) and all(item.get("status") == "READY" for item in closures)
        done("closure", ready)
        if phase == "closures_blocked":
            states["closure"] = "attention"
        done("units", bool(_report(directory, "native_unit_plan.json")) or bool(_rows(conn, "agent_tasks", directory.name)))
        units = [row for row in tasks if row.get("scope_type") in {"unit", "component"}]
        unit_plan = _report(directory, "native_unit_plan.json")
        labels = {item["unit_id"]: item.get("logical_id", item["unit_id"]) for item in unit_plan.get("units", [])} if isinstance(unit_plan, dict) else {}
        for row in units:
            history = [item for item in attempts if item["category"] == "unit" and item["identity"] == row["scope_id"]]
            state = _task_status(row["status"])
            children = [("generate", "Generate", "pending", []), ("validate", "Validate", "pending", []),
                        ("compile", "Compile", "pending", []), ("test", "Tests", "pending", [])]
            if state == "completed":
                children = [(key, title, "completed", []) for key, title, _, _ in children]
            elif history:
                latest = max(history, key=lambda item: item["created_at"])
                failure = _failure_step(latest.get("error"), _json(latest["request_json"]))
                failure = failure if failure in {"compile", "test"} else "validate"
                position = [item[0] for item in children].index(failure if latest.get("response") else "generate")
                children = [(key, title, "completed" if index < position else state if index == position else "pending", [])
                            for index, (key, title, _, _) in enumerate(children)]
            label = _json(history[-1]["request_json"]).get("logical_id") if history else None
            extra.setdefault("convert", []).append((row["scope_id"], label or labels.get(row["scope_id"], row["scope_id"]), state, children))
        if units:
            states["convert"] = _aggregate([_task_status(row["status"]) for row in units])
        done("report", run_report_path(directory, "native_bundle_results.json").is_file() or run_report_path(directory, "managed_conversion_results.json").is_file())
    elif stage == "component_review":
        done("gather", bool(_rows(conn, "generated_artifacts", directory.name)) or any(row["category"] == "unit" for row in snapshots))
        reviews = [row for row in snapshots if row["category"] == "review" and "/" not in row["identity"]]
        if reviews:
            states["review"] = _aggregate(["completed" if _json(row["data_json"]).get("approved") else "attention" for row in reviews])
        done("build", bool(reviews) and all(row["status"] == "accepted" for row in reviews) and any(row["category"] == "unit" for row in snapshots))
        done("report", run_report_path(directory, "gate_2_report.txt").is_file())
    elif stage == "operation_assembly_and_review":
        _assembly(states, extra, snapshots, attempts, tasks, phase)
        done("review.report", run_report_path(directory, "gate_3_report.txt").is_file())
    elif stage == "service_generation_and_validation":
        done("gather", run_report_path(directory, "gate_3_report.txt").is_file())
        rows = _rows(conn, "service_generation_checkpoints", directory.name)
        if rows:
            results = [_json(row["validation_json"]) for row in rows]
            for key in ("generate.wrappers", "generate.dependencies"):
                done(key, all(value.get("generation_output") for value in results))
            for key, field in (("guard", "ibm_guard_passed"), ("compile", "build_passed"), ("package", "package_passed")):
                done("validate." + key, all(value.get(field) for value in results))
            done("validate.test", all(value.get("test_status") == "passed" for value in results))
            for key, field in (("xml", "xml_compatibility"), ("equivalence", "behavioral_equivalence")):
                done("runtime." + key, all(value.get(field) == "passed" for value in results))
            for value in results:
                for key in ("compile", "test", "package"):
                    if value.get(key + "_failed"):
                        states["validate." + key] = "attention"
        done("report", run_report_path(directory, "service_validation_results.json").is_file())
    else:
        delivery = _report(directory, "delivery_manifest.json")
        done("evidence", bool(delivery) and not delivery.get("blockers"))
        if delivery.get("blockers"):
            states["evidence"] = "attention"
        done("delivery.deployment", any(row.get("artifact_kind") == "deployment_manifest" and row.get("status") == "converted" for row in _rows(conn, "generated_artifacts", directory.name)))
        done("delivery.docs", bool(delivery.get("operations")))
        done("report", run_report_path(directory, "final_report.md").is_file())
    gate = {"migration_planning": 1, "component_review": 2, "operation_assembly_and_review": 3, "final_validation": 4}.get(stage)
    if gate and (phase.startswith("gate_") or phase in {"migration_approved", "dry_run_complete"}):
        key = "review.approval" if gate == 3 else "approval"
        states[key] = "completed" if phase in {"migration_approved", "dry_run_complete"} else "attention" if status in {"blocked", "stopped", "failed"} else "current"
    nodes = []
    for key, title, children in SUBSECTIONS[stage]:
        nested = [(child, label, states.get(key + "." + child, "pending"), []) for child, label in children]
        nested.extend(extra.get(key, []))
        state = states.get(key, _aggregate([child[2] for child in nested]))
        nodes.append((key, title, state, nested))
    # Old checkpoints may lack detailed evidence. Show an active subsection without
    # falsely marking earlier work completed, and identify it as checkpoint-level.
    if not any(node[2] in {"attention", "current"} for node in nodes):
        for index, (key, title, state, children) in enumerate(nodes):
            if state == "pending":
                nodes[index] = (key, title + " (checkpoint detail unavailable)",
                                "attention" if status in {"failed", "blocked", "stopped"} else "current", children)
                break
    return nodes


def subsection_lines(nodes, depth=1):
    """Render the same four markers with indentation for nested subtasks."""
    markers = {"completed": "[V]", "current": "→", "pending": "[ ]", "attention": "!"}
    for number, (_, title, state, children) in enumerate(nodes, 1):
        yield "    " * depth + f"{markers[state]} {number}. {title}"
        yield from subsection_lines(children, depth + 1)
