"""Report observed branch outcomes and node paths without claiming exhaustive coverage."""


def boundary_coverage(boundary, observations):
    branch_items = {item.id: item for item in boundary.parser_checklist.items if item.kind == 'branch'}
    nodes = {node.id for node in boundary.reachable_slice.nodes}
    seen, paths, entered = {}, [], set()
    for observation in observations:
        path = []
        for probe in observation.probes:
            identity, outcome = probe['id'], probe['outcome']
            if identity in nodes: entered.add(identity)
            if identity in branch_items:
                seen.setdefault(identity, set()).add(outcome); path.append((identity, outcome))
        paths.append(dict(case_id=observation.case_id, branch_path=path))
    coverage = []
    preparation=getattr(boundary,'configuration_preparation',{})
    if preparation and (preparation.get('configuration_hash')!=boundary.configuration_hash or
                        preparation.get('source_manifest_hash')!=boundary.source_manifest_hash):
        raise ValueError('Configured coverage preparation belongs to another source/configuration revision')
    fixed=preparation.get('branches',{})
    conflicts=[]
    for identity, item in sorted(branch_items.items()):
        expected = {'true', 'false'} if item.detail in {'if', 'ternary', 'short_circuit', 'while_guard', 'for_guard', 'do_guard', 'foreach', 'assert', 'switch_guard'} else {'evaluated'} if item.detail == 'switch' else {'entered'}
        observed = seen.get(identity, set())
        proof=fixed.get(identity)
        excluded=expected-set(proof['allowed_outcomes']) if proof else set()
        if observed & excluded:conflicts.append(identity)
        coverage.append(dict(checklist_id=identity, detail=item.detail, source_file=item.source_file,
            condition=item.properties.get('condition'),source_identity=item.source_identity,code_node_id=item.code_node_id,
            start_line=item.start_line, expected_outcomes=sorted(expected), observed_outcomes=sorted(observed),
            unexercised_outcomes=sorted(expected - observed - excluded),
            configuration_excluded_outcomes=sorted(excluded),configuration_proof=proof))
    instrumented = {node.id for node in boundary.reachable_slice.nodes if node.kind in {'method', 'constructor', 'static_initializer', 'instance_initializer'}}
    return dict(branches=coverage, observed_paths=paths, entered_code_nodes=sorted(entered),
        unentered_instrumented_code_nodes=sorted(instrumented - entered), unprobed_code_nodes=sorted(nodes - instrumented), observed_checklist_ids=sorted(seen),
        unobserved_checklist_ids=sorted({item.id for item in boundary.parser_checklist.items} - set(seen)),
        unresolved_edges=[edge.model_dump(mode='json') for edge in boundary.reachable_slice.edges if edge.unbounded and edge.id not in preparation.get('dispatches',{})],
        configured_dispatches=preparation.get('dispatches',{}),configuration_proof_conflicts=conflicts,
        note='Only executed probes establish observed outcomes; entered methods do not prove every contained item executed.',
        exhaustive=False)

