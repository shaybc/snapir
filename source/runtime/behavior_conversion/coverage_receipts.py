"""Validate coverage and bounded exploration from immutable source inventory and actual probes."""
from types import SimpleNamespace
import json
from models.reachable_call_edge import ReachableCallEdge
from models.boundary_observation import BoundaryObservation
from tools.behavior_verification.boundary_coverage import boundary_coverage
from tools.behavior_verification.coverage_expansion import VERSION


def coverage_inventory(boundary):
    """Retain only source identities/conditions needed by the canonical coverage calculator."""
    names=('id','detail','source_file','start_line','source_identity','code_node_id')
    return dict(branches=[dict(**{name:getattr(item,name) for name in names},kind='branch',
        properties={'condition':item.properties.get('condition')}) for item in boundary.parser_checklist.items if item.kind=='branch'],
        nodes=[dict(id=node.id,kind=node.kind) for node in boundary.reachable_slice.nodes],
        edges=[edge.model_dump(mode='json') for edge in boundary.reachable_slice.edges if edge.unbounded],
        configuration_preparation=getattr(boundary,'configuration_preparation',{}))


def require_coverage_evidence(structure,receipt,report,policy):
    """No reported coverage gain or expansion counter can substitute for executed evidence."""
    inventory=structure['coverage_inventory']
    boundary=SimpleNamespace(source_manifest_hash=structure.get('source_manifest_hash'),configuration_hash=structure.get('configuration_hash'),
        parser_checklist=SimpleNamespace(items=[SimpleNamespace(**item) for item in inventory['branches']]),
        configuration_preparation=inventory.get('configuration_preparation',{}),
        reachable_slice=SimpleNamespace(nodes=[SimpleNamespace(**node) for node in inventory['nodes']],
            edges=[ReachableCallEdge.model_validate(edge) for edge in inventory['edges']]))
    expected=boundary_coverage(boundary,[BoundaryObservation.model_validate(case['legacy']) for case in report.cases])
    # Non-branch checklist inventory remains diagnostic; it is not an acceptance requirement.
    fields=('branches','observed_paths','entered_code_nodes','unentered_instrumented_code_nodes','unprobed_code_nodes','unresolved_edges')
    if any(json.dumps(expected[field],sort_keys=True)!=json.dumps(report.coverage.get(field),sort_keys=True) for field in fields):
        raise ValueError('Coverage does not match retained original probes')
    if any(expected[field]!=report.coverage.get(field,default) for field,default in
           (('configured_dispatches',{}),('configuration_proof_conflicts',[]))):
        raise ValueError('Configured coverage proof does not match retained preparation')
    if expected['configuration_proof_conflicts']:
        raise ValueError('Executed outcomes contradict configured preparation')
    exploration=report.execution_environment.get('coverage_expansion',{})
    if (structure['coverage_expansion_version']!=VERSION or exploration.get('version')!=VERSION
        or exploration!=receipt.get('coverage_expansion')):raise ValueError('Coverage expansion evidence changed or is unsupported')
    rounds=exploration['rounds'];ids=[identity for batch in rounds for identity in batch['case_ids']]
    if (len(rounds)>policy.coverage_expansion_rounds or len(ids)>policy.coverage_expansion_cases
        or len(ids)!=len(set(ids)) or any(len(batch['case_ids'])>policy.coverage_expansion_batch_size for batch in rounds)
        or exploration['additional_cases']!=len(ids)
        or exploration['executed_additional_cases']!=len(ids)
        or not set(ids)<={case['case']['case_id'] for case in report.cases}
        or exploration['remaining_gaps']!=[b for b in expected['branches'] if b['unexercised_outcomes']]
        or exploration['coverage_gaps_block']!=policy.require_branch_coverage):
        raise ValueError('Coverage expansion exceeded its policy or does not match executed cases')
