"""Apply explicit operation-scoped dependency choices to final service builds."""


def operation_dependency_pins(profile, channel, operation_id):
    """Return configured pins for this operation, rejecting conflicting artifact choices."""
    pins = list(profile.service_maven_dependencies.get(channel + "/" + operation_id, []))
    seen = {}
    for pin in pins:
        key = (pin.group_id, pin.artifact_id)
        if key in seen and seen[key] != pin:
            raise ValueError("Conflicting service dependency pins for " + ":".join(key))
        seen[key] = pin
    return list(seen.values())


def apply_dependency_pins(proposals, pins):
    """Use configured coordinates and scope while retaining every required API check."""
    selected = {(pin.group_id, pin.artifact_id): pin.model_copy(deep=True) for pin in pins}
    ordinary = []
    for proposal in proposals:
        key = (proposal.group_id, proposal.artifact_id)
        if key not in selected:
            ordinary.append(proposal)
        else:
            pin = selected[key]
            pin.required_classes = sorted(set(pin.required_classes + proposal.required_classes))
    return [*ordinary, *selected.values()]
