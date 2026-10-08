from __future__ import annotations

from dataclasses import dataclass

from models.conversion_models import RoutingPlan, RoutingStep


@dataclass(frozen=True)
class TraceScenario:
    """A runtime path to exercise during equivalence validation."""

    name: str
    step_sequence: list[str]
    terminal_rc_values: dict[str, str]
    request_xml_template: str


def derive_trace_scenarios(routing_plan: RoutingPlan) -> list[TraceScenario]:
    """Derive one trace scenario for each distinct terminal path."""
    if not routing_plan.steps:
        return [_success_scenario(routing_plan.operation_id, [], {})]
    steps_by_index = {step.step_index: step for step in routing_plan.steps}
    terminal_paths = []
    _walk_paths(steps_by_index, steps_by_index.get(0), [], {}, terminal_paths)
    scenarios = []
    seen_signatures = set()
    for sequence, terminal_rcs in terminal_paths:
        signature = tuple(sequence)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        scenarios.append(
            TraceScenario(
                name=_scenario_name(sequence, terminal_rcs, steps_by_index),
                step_sequence=sequence,
                terminal_rc_values=terminal_rcs,
                request_xml_template=_request_template(routing_plan.operation_id, sequence),
            )
        )
    if not scenarios:
        scenarios.append(_success_scenario(routing_plan.operation_id, [routing_plan.steps[0].step_id], {}))
    return scenarios


def _walk_paths(
    steps_by_index: dict[int, RoutingStep],
    step: RoutingStep | None,
    sequence: list[str],
    rc_values: dict[str, str],
    terminal_paths: list[tuple[list[str], dict[str, str]]],
) -> None:
    if step is None or step.step_id in sequence:
        terminal_paths.append((sequence, rc_values))
        return
    current_sequence = [*sequence, step.step_id]
    if not step.transitions:
        terminal_paths.append((current_sequence, rc_values))
        return
    for rc, target in step.transitions.items():
        next_rc_values = {**rc_values, step.step_id: str(rc)}
        if str(target) == "end":
            terminal_paths.append((current_sequence, next_rc_values))
        elif isinstance(target, int):
            _walk_paths(steps_by_index, steps_by_index.get(target), current_sequence, next_rc_values, terminal_paths)
        elif str(target).isdigit():
            _walk_paths(steps_by_index, steps_by_index.get(int(target)), current_sequence, next_rc_values, terminal_paths)
        else:
            terminal_paths.append((current_sequence, next_rc_values))


def _scenario_name(
    sequence: list[str],
    terminal_rcs: dict[str, str],
    steps_by_index: dict[int, RoutingStep],
) -> str:
    if terminal_rcs and all(rc == "0" for rc in terminal_rcs.values()):
        return "success"
    terminal_step_id = sequence[-1] if sequence else "operation"
    terminal_rc = terminal_rcs.get(terminal_step_id)
    terminal_step = next((step for step in steps_by_index.values() if step.step_id == terminal_step_id), None)
    if terminal_step and terminal_rc and f"on{terminal_rc}Return" in terminal_step.return_body_switches:
        return f"business_error_{terminal_step_id}"
    return f"technical_error_{terminal_step_id}"


def _request_template(operation_id: str, sequence: list[str]) -> str:
    steps = "".join(f"<step>{step_id}</step>" for step_id in sequence)
    return f"<{operation_id}TraceRequest>{steps}</{operation_id}TraceRequest>"


def _success_scenario(operation_id: str, sequence: list[str], rc_values: dict[str, str]) -> TraceScenario:
    return TraceScenario(
        name="success",
        step_sequence=sequence,
        terminal_rc_values=rc_values,
        request_xml_template=_request_template(operation_id, sequence),
    )
