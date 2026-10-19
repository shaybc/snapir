"""Check test-plan coverage against original routes and render its readable report."""

from pathlib import Path
from tools.component_inventory_tools.identity import stable_id
from runtime.workspace_paths import run_report_path


def validate_route_plan(plan, routing, requirements):
    """Reject invented/missing edges, incomplete paths and unsupported coverage claims."""
    if plan.unresolved_questions:
        raise ValueError("Unresolved route-test evidence: " + "; ".join(plan.unresolved_questions))
    identifiers = [scenario.scenario_id for scenario in plan.scenarios]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Route-test scenario IDs must be unique")
    original = {(source, outcome, str(target)) for source, edges in routing.items() for outcome, target in edges.items()}
    covered, covered_requirements = set(), set()
    entry = next(iter(routing), None)
    for scenario in plan.scenarios:
        if not set(scenario.covers).issubset(requirements):
            raise ValueError("Scenario claims unknown requirements: " + scenario.scenario_id)
        edges = [(edge.source, edge.outcome, edge.target) for edge in scenario.routes]
        if not set(edges).issubset(original):
            invalid = sorted(set(edges) - original)
            sources = {edge[0] for edge in invalid}
            allowed = sorted(edge for edge in original if edge[0] in sources)
            raise ValueError("Scenario invents an original routing edge: " + scenario.scenario_id
                + "; invalid edges: " + str(invalid) + "; allowed edges for these sources: " + str(allowed)
                + ". Copy the exact source, outcome key and target from routing_graph; do not shorten outcome keys.")
        if original and (not edges or edges[0][0] != entry or edges[-1][2] in routing
                or any(left[2] != right[0] for left, right in zip(edges, edges[1:]))):
            raise ValueError("Scenario must follow a continuous entry-to-terminal original path: " + scenario.scenario_id)
        nodes = {edge[0] for edge in edges}
        if any(name.startswith("route-") and name.removeprefix("route-") not in nodes for name in scenario.covers):
            raise ValueError("Scenario route coverage is not supported by its path: " + scenario.scenario_id)
        covered.update(edges)
        covered_requirements.update(scenario.covers)
    if original - covered:
        raise ValueError("Route-test plan omits original edges: " + str(sorted(original - covered)))
    if set(requirements) - covered_requirements:
        raise ValueError("Route-test plan omits requirements: " + ", ".join(sorted(set(requirements) - covered_requirements)))


def write_route_plan(directory, identity, plan):
    """Write JSON and Markdown views of the same validated scenario plan."""
    folder = run_report_path(Path(directory), "gate_3_report.txt").parent / "route_test_plans"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (stable_id(identity)[:16] + ".md")
    lines = ["# Route-test plan: " + identity, ""]
    for number, scenario in enumerate(plan.scenarios, 1):
        lines.extend([f"## {number}. {scenario.description}", "", "Scenario: " + scenario.scenario_id,
            "", "Coverage: " + ", ".join(scenario.covers), "", "Inputs:"])
        lines.extend("- " + item for item in scenario.inputs)
        lines.extend(["", "Collaborator setup:"])
        lines.extend("- " + item for item in scenario.dependency_setup)
        lines.extend(["", "Expected outcome: " + scenario.expected_outcome, "", "Expected side effects:"])
        lines.extend("- " + item for item in scenario.expected_side_effects)
        lines.extend(["", "Original path:"])
        lines.extend(f"- {edge.source} → {edge.outcome} → {edge.target}" for edge in scenario.routes)
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.with_suffix(".json").write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
