"""Write linked Markdown Gate One reports and bind approval to the entire bundle."""

import json
import logging
import re
from pathlib import Path

from agents.migration_planning.batch_composition import load_composition, composition_lines
from agents.migration_planning.gate_report import planning_summary, component_and_routing_report
from runtime.workspace_paths import run_report_path


def _markdown(text):
    """Preserve readable detail lines while recognizing report section headings."""
    lines = []
    for line in text.splitlines():
        if line.startswith("<"):
            lines.append(line)
        elif line and line.isupper() and not line.startswith("-"):
            lines.append("## " + line)
        elif "|" in line:
            lines.append(line)
        else:
            lines.append(line + ("  " if line else ""))
    return "\n".join(lines) + "\n"


def write_gate_one_reports(directory, conn, config, profile, plan, operations, libraries):
    """Produce a concise overview with operation details and shared ownership links."""
    directory = Path(directory)
    report_root = directory / "reports" / "2_migration_planning" / "gate_1"
    operation_root = report_root / "operations"
    operation_root.mkdir(parents=True, exist_ok=True)
    inventory = load_composition(conn, config.run_id)
    overview = ["# Gate One: Review the migration plan", "",
                "Do you approve the selected operations, batch order, and proposed component ownership?",
                "Approval accepts this plan as the basis for conversion.", "",
                "## Migration scope", "",
                "Selected channels: " + ", ".join(config.target_channels), "",
                "Requested operations: " + (", ".join(config.include_operations) if config.include_operations else "All eligible operations in the selected channels"), "",
                "Excluded operations: " + (", ".join(config.exclude_operations) if config.exclude_operations else "None"), "",
                f"Operations planned: {plan.total_operations}; batches: {len(plan.batches)}.", ""]
    paths = []
    number = 0
    for index, batch in enumerate(plan.batches, 1):
        overview.extend([f"## Batch {index}" + (" — Pilot: first conversion batch" if batch.is_pilot else ""), ""])
        overview.extend(composition_lines(batch.task_packets, inventory, include_details=False))
        overview.extend(["", "Operation | Target | Classification | Review", "--- | --- | --- | ---"])
        for packet in batch.task_packets:
            number += 1
            slug = re.sub(r"[^A-Za-z0-9_-]+", "-", packet.channel + "-" + packet.operation_id).strip("-")[:100] or "operation"
            relative = f"reports/2_migration_planning/gate_1/operations/{number:04d}-{slug}.md"
            paths.append(relative)
            single_batch = batch.model_copy(update={"task_packets": [packet]})
            single_plan = plan.model_copy(update={"batches": [single_batch], "total_operations": 1})
            single_config = config.model_copy(update={"target_channels": [packet.channel], "include_operations": [packet.operation_id]})
            evidence = [item for item in operations if item.get("channel") == packet.channel and item["operation_id"] == packet.operation_id]
            detail = planning_summary(single_plan, single_config, evidence, inventory, collapsible=True)
            detail += "\n" + component_and_routing_report(conn, config.run_id, single_plan, libraries, include_ownership=False, collapsible=True)
            content = "# " + packet.channel + " / " + packet.operation_id + "\n\n[Gate One overview](../../gate_1_report.md) · [Shared-library decisions](../shared_libraries.md)\n\n" + _markdown(detail)
            (directory / relative).write_text(content, encoding="utf-8")
            overview.append(f"{packet.channel} / {packet.operation_id} | {packet.target_language.value} | {packet.group.value.replace('_', ' ')} | [Operation details](gate_1/operations/{number:04d}-{slug}.md)")
        overview.append("")
    shared_path = "reports/2_migration_planning/gate_1/shared_libraries.md"
    paths.append(shared_path)
    shared = component_and_routing_report(conn, config.run_id, plan, libraries, include_routing=False, collapsible=True)
    (directory / shared_path).write_text("# Shared-library decisions\n\n[Gate One overview](../gate_1_report.md)\n\n" + _markdown(shared), encoding="utf-8")
    blocked = [item for item in operations if item.get("has_blocked_context")]
    overview.extend(["## Review and decision", "",
                     f"Operations with blocked context dependencies: {len(blocked)}.", "",
                     "[Review shared-library decisions](gate_1/shared_libraries.md)", "",
                     "Review the scope and batch order above, each operation's dependencies and outcomes, and shared-library ownership.", "",
                     "Choose **Approve a gate** to accept the proposal, then **Resume a migration** to continue. Choose **Reject a gate** if changes or further evidence are needed.", "",
                     "Approval policy: " + profile.gate_policies.get("1", "human") + ".", "",
                     "Your decision is bound to the overview and all linked reports.", ""])
    overview_path = run_report_path(directory, "gate_1_report.md")
    overview_path.write_text("\n".join(overview), encoding="utf-8")
    (report_root / "manifest.json").write_text(json.dumps(paths, indent=2), encoding="utf-8")
    logging.getLogger(__name__).info("Migration planning — Gate One review overview: %s", overview_path)
    return read_gate_one_reports(directory)


def read_gate_one_reports(directory):
    """Read every declared report deterministically for the existing approval hash."""
    directory = Path(directory).resolve()
    manifest_path = directory / "reports" / "2_migration_planning" / "gate_1" / "manifest.json"
    paths = json.loads(manifest_path.read_text(encoding="utf-8"))
    contents = {"reports/2_migration_planning/gate_1_report.md": run_report_path(directory, "gate_1_report.md").read_text(encoding="utf-8")}
    for relative in paths:
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory / "reports" / "2_migration_planning" / "gate_1") or path.suffix != ".md":
            raise ValueError("Invalid Gate One report path")
        contents[relative] = path.read_text(encoding="utf-8")
    return json.dumps(contents, ensure_ascii=False, sort_keys=True)
