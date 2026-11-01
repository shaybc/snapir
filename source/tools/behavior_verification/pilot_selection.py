"""Select a repeatable, source-bound pilot without filtering away difficult units."""
from collections import defaultdict
from models.unit_verification_boundary import UnitVerificationBoundary
from tools.behavior_verification.boundary_contracts import boundary_contract, digest


def select_pilot(preparation, analysis, *, dataset_type, per_group=20):
    """Round-robin implementation/direction/branch shapes; keep incomplete analysis eligible."""
    if dataset_type not in {'production','bank_demo'} or not 1 <= per_group <= 1000:
        raise ValueError('Specify production or bank_demo and a positive bounded sample size')
    candidates = {'formats':[], 'steps':[]}
    seen = set()
    for operation, prepared in sorted(preparation['operations'].items()):
        for unit in prepared.get('units', []):
            identity = unit['unit_id']
            if identity in seen: raise ValueError('Duplicate pilot unit: ' + identity)
            seen.add(identity)
            boundary = UnitVerificationBoundary.model_validate(analysis['boundaries'][identity])
            original = boundary_contract(unit)
            fields = ('unit_id','unit_fingerprint','configuration_hash','source_manifest_hash')
            if any(getattr(boundary,key) != getattr(original,key) for key in fields):
                raise ValueError('Boundary evidence does not match preparation: ' + identity)
            checklist = boundary.parser_checklist
            branches = [item for item in checklist.items if item.kind == 'branch'] if checklist else []
            shape = dict(kind=boundary.kind, implementation=boundary.implementation_class,
                branch_shapes=sorted({item.detail for item in branches}),
                branch_size='none' if not branches else '1-5' if len(branches)<=5 else '6+',
                setup_classes=sorted(set(boundary.setup_class_roots)),
                external_calls=bool(boundary.reachable_slice and boundary.reachable_slice.external_signatures),
                analysis_status=boundary.analysis_status)
            record = dict(unit_id=identity, logical_id=unit.get('logical_id',identity), operation=operation,
                kind=boundary.kind, unit_fingerprint=boundary.unit_fingerprint, configuration_hash=boundary.configuration_hash,
                source_manifest_hash=boundary.source_manifest_hash, shape=shape, shape_id=digest(shape),
                literal_inventory_available=checklist is not None and checklist.status=='extracted',
                literal_item_ids=sorted(item.id for item in checklist.items if item.kind=='literal') if checklist else [])
            candidates['steps' if boundary.kind=='configured_step' else 'formats'].append(record)
    selected, availability = [], {}
    for group, records in candidates.items():
        buckets = defaultdict(list)
        for record in sorted(records,key=lambda item:digest(item['unit_id'])): buckets[record['shape_id']].append(record)
        chosen = []
        while len(chosen)<per_group and any(buckets.values()):
            for key in sorted(buckets):
                if buckets[key] and len(chosen)<per_group: chosen.append(buckets[key].pop(0))
        selected.extend(chosen)
        availability[group] = dict(requested=per_group, available=len(records), selected=len(chosen), shortfall=max(0,per_group-len(chosen)))
    if not selected: raise ValueError('No configured pilot units available')
    plan = dict(schema_version='verification-pilot-v1', dataset_type=dataset_type,
        selection_method='deterministic shape round-robin; incomplete analysis is not excluded',
        analysis_tool_hash=analysis.get('analysis_tool_hash'), availability=availability,
        selected_units=selected, operations=sorted({item['operation'] for item in selected}),
        note='Convert these operations through the existing pipeline. Dependencies may add units; metrics use only this sample.')
    return dict(**plan, sample_hash=digest(plan))


def validate_pilot(plan):
    """Reject an edited/tampered manifest rather than silently changing the measurement denominator."""
    if plan.get('schema_version')!='verification-pilot-v1' or plan.get('dataset_type') not in {'production','bank_demo'}:
        raise ValueError('Unknown pilot manifest')
    if plan.get('sample_hash') != digest({key:value for key,value in plan.items() if key!='sample_hash'}):
        raise ValueError('Pilot sample manifest changed')
    identities=[item['unit_id'] for item in plan['selected_units']]
    if not identities or len(identities)!=len(set(identities)): raise ValueError('Pilot must contain distinct units')
