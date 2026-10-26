"""Adapt prepared occurrences to native workflow requests without label-keyed routing."""

from copy import deepcopy
import json

from models.scoped_configured_unit import ScopedConfiguredUnit


def native_inputs(report):
    """Return engine inputs using occurrence IDs and explicit terminal edges."""
    closures, by_operation, units, bindings = [], {}, {}, {}
    for key, item in sorted(report['operations'].items(), key=lambda pair: (pair[1]['dependency_wave']['wave'], pair[0])):
        if item['status'] != 'prepared':
            raise ValueError('Native generation requires prepared context: ' + key)
        workflow = deepcopy(item['behavior_request'])
        workflow['service_contract'].pop('status', None)
        notes = {step['note']: step['occurrence_id'] for step in workflow['steps']}
        if not notes or workflow['entry_step_note'] != workflow['steps'][0]['note']:
            raise ValueError('Native workflow requires an evidenced first occurrence: ' + key)
        routing = {}
        for step in workflow['steps']:
            routing[step['occurrence_id']] = {}
            for outcome, target in step['routes'].items():
                if target is not None and target not in notes:
                    raise ValueError('Native route target is outside selected occurrences: ' + str(target))
                routing[step['occurrence_id']][outcome] = 'end' if target is None else notes[target]
        workflow['source_routing_graph'] = workflow['routing_graph']
        workflow['routing_graph'] = routing
        workflow['conversion_enabled'] = True
        workflow['requirements'] = {name: value if isinstance(value, str) else json.dumps(value, sort_keys=True)
                                    for name, value in sorted(workflow['requirements'].items())}
        own = [ScopedConfiguredUnit.model_validate(unit) for unit in item['units']]
        if any(unit.consumers != [key] or unit.operation_identity != workflow['operation_identity'] for unit in own):
            raise ValueError('Configured units disagree with consuming context: ' + key)
        by_operation[key] = own
        for unit in own:
            if unit.unit_id in units:
                raise ValueError('Scoped configured unit is shared between execution contexts')
            units[unit.unit_id] = unit
        bindings[key] = {step['occurrence_id']: workflow['unit_bindings'][step['note']] for step in workflow['steps']}
        bindings[key].update({name: identity for name, identity in sorted(workflow['unit_bindings'].items()) if name not in notes})
        closures.append(dict(operation_id=workflow['operation_id'], channel=workflow['channel'],
            operation_identity=workflow['operation_identity'], definition_id=workflow['definition_id'],
            scoped_workflow=workflow, routing_graph=routing, operation_calls=workflow['operation_calls'],
            composer_behavior_evidence=workflow['composer_behavior_evidence']))
    return closures, by_operation, units, bindings
