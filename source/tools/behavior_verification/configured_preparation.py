"""Validate tool-owned configured proofs and retain their original source/configuration scope."""
VERSION='configured-coverage-preparation-v1'


def retain_preparation(boundary,plan):
    """Unknown preparation is blocking evidence, never an inferred exclusion."""
    if plan.get('version')!=VERSION:
        raise ValueError('Rebuild the source analysis tool for configured coverage preparation')
    if (plan.get('configuration_hash',boundary.configuration_hash)!=boundary.configuration_hash or
            plan.get('source_manifest_hash',boundary.source_manifest_hash)!=boundary.source_manifest_hash):
        raise ValueError('Configured preparation source/configuration revision changed')
    items={item.id:item for item in boundary.parser_checklist.items}
    nodes={node.id:node for node in boundary.reachable_slice.nodes}
    edges={edge.id:edge for edge in boundary.reachable_slice.edges}
    for identity,proof in plan['branches'].items():
        item=items.get(identity)
        if item is None or item.kind!='branch' or proof.get('code_node_id')!=item.code_node_id:
            raise ValueError('Configured branch proof is outside the parser inventory')
        if proof.get('source_identity')!=item.source_identity or proof.get('source_hash')!=item.source_hash:
            raise ValueError('Configured branch proof source changed')
        if proof.get('rule')!='pure_tag_setup_or_private_setup_only_field' or proof.get('condition')!=item.properties.get('condition'):
            raise ValueError('Configured branch proof predicate changed or rule is unsupported')
        if proof.get('allowed_outcomes') not in (['true'],['false']) or proof.get('occurrences',0)<1:
            raise ValueError('Configured branch proof is not a fixed predicate')
    for identity,proof in plan['dispatches'].items():
        edge=edges.get(identity);node=nodes.get(proof.get('code_node_id'))
        if edge is None or node is None or edge.from_id!=node.id or not proof.get('candidates') or not set(proof['candidates'])<=set(edge.candidates):
            raise ValueError('Configured dispatch proof is outside the original call graph')
        if proof.get('source_identity')!=node.source_identity or proof.get('source_hash')!=node.source_hash:
            raise ValueError('Configured dispatch proof source changed')
        if (proof.get('rule')!='private_final_list_trusted_tree_registration' or
                not set(proof.get('configured_child_types',[]))<=set(boundary.setup_class_roots)):
            raise ValueError('Configured dispatch target is outside the configured tree')
    boundary.configuration_preparation={**plan,'source_manifest_hash':boundary.source_manifest_hash,
        'configuration_hash':boundary.configuration_hash}
