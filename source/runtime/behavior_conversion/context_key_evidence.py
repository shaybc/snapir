"""Share original Java and resolved XML context-key evidence across binding checks."""
from copy import deepcopy
from tools.behavior_verification.thin_path_binding import configured_fields


def with_context_key_evidence(unit, inventory):
    """Return detached key records from parsed originals and an already-resolved configuration.

    XML field paths are retained as provenance, not inferred from native DTO names.
    Partition callers must resolve their trusted subtree before calling this utility.
    Missing/cyclic referenced definitions remain errors from configured_fields.
    """
    keys=deepcopy(inventory.get('context_keys',[]))
    if unit.get('effective_configuration') is not None:
        for field in configured_fields(unit):
            evidence=dict(name=field['context_key'],source='resolved_configuration',
                path=field['path'],unit_id=unit.get('unit_id'))
            if evidence not in keys:keys.append(evidence)
    return dict(inventory,context_keys=keys)
