"""Attach deterministic original-code obligations; no AI fact extraction or executable bridge."""
from tools.behavior_verification.boundaries import build_boundary_report
from models.unit_verification_boundary import UnitVerificationBoundary
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete


CHECKLIST_INSTRUCTION = '''Each checklist source_ref indexes slice_sources; its span locates the exact
original syntax within that source fragment. Candidate references likewise point to source entries or
explicit external signatures. These are lossless references, not AI summaries or dropped obligations.
Answer every parser checklist ID exactly once in checklist_answers, bound to
the supplied unit_id/source_manifest_hash/configuration_hash. Implemented items cite exact main-Java
path/excerpts, including helpers; one excerpt may cover several items. not_applicable needs a supported
parser proof or a separately recorded approval; matching samples and method names are not proof.
Unresolved items remain verification incomplete. Do not return AI-written behavior facts.
Return verification_binding describing an actual public native method from unit_contract.apis.
Use only declarative XML/context/object argument bindings and actual typed-result/argument getters;
never generate executable harness adapters or expected responses. XML entry arguments are String
facades invoking your actual Jackson parser/mapper. Object inputs use public constructors and typed
setters. context_writes project actual state in source-observable order; presence getters preserve
missing/null distinctions and argument state can expose partial writes on exceptions. Set output=none
for request mappers; response methods return XML strings; step output must preserve the return code.
Expose runtime settings through explicit native collaborators and settings_bindings, preserving all
source-dependent conditions. Never hardcode runtime inputs, outputs or library-default behavior.
All code will be built/tested and compared at the original unit boundary on the same controlled inputs.
Fix verification_feedback item IDs and failing cases without weakening checks or approved APIs.'''


def attach_verification(payload, *, collect_facts=True):
    """Use only the configured unit's already-selected original sources and parser evidence."""
    unit = dict(payload)
    report = build_boundary_report(dict(operations={'unit': dict(units=[unit])}),
        mappings={'unit':payload.get('component_default_mapping',{})},collect_checklists=collect_facts)
    boundary = UnitVerificationBoundary.model_validate(report['boundaries'][unit['unit_id']])
    if boundary.analysis_status != 'identified' or collect_facts and (boundary.parser_checklist is None or boundary.parser_checklist.status != 'extracted'):
        raise VerificationIncomplete(dict(stage='parser', unit_id=unit['unit_id'], issues=boundary.issues or ['Parser checklist unavailable']))
    result = dict(payload)
    for key in ('behavior_specification', 'behavior_specification_fingerprint', 'behavior_evidence'):
        result.pop(key, None)
    references = {node.id: index for index, node in enumerate(boundary.reachable_slice.nodes)}
    checklist = dict(schema_version='parser-checklist-delivery-v1',
        source_manifest_hash=boundary.source_manifest_hash, configuration_hash=boundary.configuration_hash, items=[])
    for item in boundary.parser_checklist.items if boundary.parser_checklist is not None else ():
        delivered = dict(id=item.id, kind=item.kind, detail=item.detail, syntax_type=item.syntax_type, source_ref=references[item.code_node_id],
                         span=[item.start_line,item.start_column,item.end_line,item.end_column])
        if item.properties: delivered['properties'] = item.properties
        if item.arguments: delivered['arguments'] = item.arguments
        if item.candidates: delivered['candidates'] = [dict(source_ref=references[value]) if value in references else
                                                     dict(external_signature=value) for value in item.candidates]
        checklist['items'].append(delivered)
    result.update(boundary=boundary.model_dump(mode='json', exclude={'parser_checklist', 'reachable_slice'}), checklist=checklist,
                  slice_sources=_slice_sources(unit, boundary), verification_version='parser-boundary-v1')
    result['analysis_tool_hash'] = report['analysis_tool_hash']
    # Whole source snapshots remain on the trusted side; generation receives complete reachable declarations.
    result.pop('sources', None)
    return result, boundary, unit


def _slice_sources(unit, boundary):
    """Preserve exact original declarations/ranges; never replace source with an AI summary."""
    sources = {item['identity']: item for item in unit['sources']}
    import hashlib
    return [dict(identity=node.id, original_identity=node.source_identity, original_content_hash=node.source_hash,
                 fragment_hash=hashlib.sha256(node.excerpt.encode()).hexdigest(), declaring_class=node.declaring_class,
                 signature=node.signature, kind=node.kind, path_certainty=node.path_certainty,
                 initialization_rule=node.initialization_rule, default_value=node.default_value,
                 start_line=node.start_line, start_column=node.start_column,
                 end_line=node.end_line, end_column=node.end_column, content=node.excerpt)
            for node in boundary.reachable_slice.nodes if node.source_identity in sources]
