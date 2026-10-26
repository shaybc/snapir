"""Cross-check selected occurrences against Composer routing without selecting by label alone."""

from tools.conversion_tools.channel_filter_tool import _is_allowed_for_channel
from tools.conversion_tools.scoped_closure.source_evidence import child_selectors


def resolve_routing(access, context, sources, steps, issue):
    """Return occurrence-keyed routes and raw per-occurrence return-body names."""
    canonical = access.canonical_steps(context)
    operation = access.resource(context, 'operations:' + context.operation_id)
    direct_steps = [(child, selector) for child, selector in child_selectors(
        sources.xml(operation), operation.evidence['source_selector']) if child.tag == 'opStep']
    source_order = {selector: index for index, (_, selector) in enumerate(direct_steps)}
    if len(canonical) != len(source_order):
        issue(context.operation_id, 'Canonical inventory does not cover every source step occurrence')
    canonical.sort(key=lambda reference: source_order.get(reference.evidence['source_selector'], len(source_order)))
    expected = []
    for position, reference in enumerate(canonical):
        element = sources.xml(reference)
        if source_order.get(reference.evidence['source_selector']) != position or int(
                reference.evidence['metadata']['step_index']) != position:
            issue(reference.note, 'Canonical source step position is inconsistent')
        if _is_allowed_for_channel(element.get('onlyFor'), context.channel):
            expected.append(reference.note)
    if expected != [step.source.note for step in steps]:
        issue(context.operation_id, 'Selected step order disagrees with source onlyFor rules')
    record = access.context_evidence(context)
    if record['entry_step_note'] != (expected[0] if expected else ''):
        issue(context.operation_id, 'Context entry differs from selected source order')
    routes, switches = {}, {}
    names = [step.source.entity_id for step in steps]
    for index, step in enumerate(steps):
        element = sources.xml(step.source)
        transitions = {key: value for key, value in element.attrib.items()
                       if key.startswith('on') and key.endswith('Do')}
        routes[step.source.note] = {}
        for condition, label in transitions.items():
            target_index = None
            if label.lower() == 'next':
                target_index = index + 1 if index + 1 < len(steps) else None
            elif label != 'end':
                target_index = next((i for i in [*range(index, len(steps)), *range(index)] if names[i] == label), None)
                if target_index is None:
                    issue(step.source.note, f'Unresolved exact-case transition {condition}: {label}')
            expected_target = steps[target_index].source.note if target_index is not None else None
            actual = step.transition_targets.get(condition)
            if actual != expected_target:
                issue(step.source.note, f'Context transition disagrees with source position: {condition}')
            routes[step.source.note][condition] = actual
        for condition in step.transition_targets.keys() - transitions.keys():
            issue(step.source.note, 'Context contains an unevidenced transition: ' + condition)
        switches[step.source.note] = {key: value for key, value in element.attrib.items()
                                     if key.startswith('on') and key.endswith('Return')}
    return routes, switches
