"""Orchestrate qualified closure inspection without enabling conversion or contract generation."""

import hashlib
import json

from models.conversion_models import ClosureBlockingIssue, ClosureStatus
from models.scoped_operation_closure import ScopedOperationClosure
from tools.composer_mapper_tools.channel_note_parser import parse_channel_note
from tools.composer_mapper_tools.scoped_vault_access import ScopedVaultAccess
from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
from tools.conversion_tools.scoped_closure.contexts import resolve_contexts, resolve_fields
from tools.conversion_tools.scoped_closure.formats import FormatResolver
from tools.conversion_tools.scoped_closure.java_origins import resolve_java_origins
from tools.conversion_tools.scoped_closure.java_dependencies import check_scoped_java_dependencies
from tools.conversion_tools.scoped_closure.routing import resolve_routing
from tools.conversion_tools.scoped_closure.source_evidence import SourceEvidence
from tools.conversion_tools.scoped_closure.state import initialize, save_closures


def build_scoped_closure(conn, operation_id, channel, run_id, composer_root, *,
                         java_project=None, classpath_index=None, profile=None, included_contexts=None):
    """Build and store only reachable qualified closures; all generation gates remain closed."""
    access = ScopedVaultAccess(conn, run_id)
    root_context = access.operation(channel, operation_id)
    sources = SourceEvidence(composer_root)
    initialize(conn)
    source_index = None
    if java_project is not None:
        from tools.source_discovery_tools import discover_java_sources
        source_index = discover_java_sources(composer_root)
    closures, pending = {}, [root_context]
    while pending:
        context = pending.pop()
        if context.operation_identity in closures:
            continue
        closure = _local_closure(access, context, sources, source_index, classpath_index, java_project, profile)
        closures[context.operation_identity] = closure
        for call in closure.calls:
            if call.get('detail'):
                continue
            # The validated manifest already chose this target in the same consuming channel.
            target = access.operation(context.channel, call['target_name'])
            if target.definition_id != call['target_definition_id']:
                raise ValueError('Imported call and target context identities disagree')
            closure.dependency_contexts.append(target.operation_identity)
            # C4 prepares only explicitly included services; published/excluded boundaries
            # are checked by the call planner, never silently added to conversion scope.
            if included_contexts is None or target.operation_identity in included_contexts:
                pending.append(target)
    for closure in closures.values():
        try:
            for relative, digest in closure.source_revisions.items():
                if file_digest(sources.path(relative)) != digest:
                    raise ValueError('Source changed while analyzing closure: ' + relative)
            for origin in closure.java_origins:
                if origin.get('status') == 'verified_source' and file_digest(origin['source_file']) != origin['source_hash']:
                    raise ValueError('Java source changed while analyzing closure: ' + origin['source_file'])
        except (ValueError, OSError) as exc:
            closure.blocking_issues.append(ClosureBlockingIssue(kind=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE,
                entity_id=closure.operation_id, detail=str(exc)))
    blocked = {identity for identity, closure in closures.items() if closure.blocking_issues}
    changed = True
    while changed:
        changed = False
        for identity, closure in closures.items():
            if identity not in blocked and any(target in blocked for target in closure.dependency_contexts):
                blocked.add(identity)
                changed = True
    for identity, closure in closures.items():
        for target in dict.fromkeys(closure.dependency_contexts):
            if target in blocked:
                closure.blocking_issues.append(ClosureBlockingIssue(kind=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE,
                    entity_id=target, detail='Called execution context has unresolved qualified dependency evidence'))
        closure.status = 'blocked' if identity in blocked else 'evidence_ready'
        facts = closure.model_dump(mode='json', exclude={'evidence_hash'})
        closure.evidence_hash = hashlib.sha256(json.dumps(facts, sort_keys=True).encode('utf-8')).hexdigest()
    save_closures(conn, closures.values())
    return closures[root_context.operation_identity]


def _local_closure(access, context, sources, source_index, classpath_index, java_project, profile):
    sources.used = {}
    closure = ScopedOperationClosure(run_id=access.run_id, operation_identity=context.operation_identity,
        operation_id=context.operation_id, channel=context.channel, definition_id=context.definition_id)

    def issue(entity, detail, kind=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE):
        item = ClosureBlockingIssue(kind=kind, entity_id=entity, detail=detail)
        if item not in closure.blocking_issues:
            closure.blocking_issues.append(item)

    try:
        record = access.context_evidence(context)
        operation = access.resource(context, 'operations:' + context.operation_id)
        element = sources.xml(operation)
        closure.operation = dict(definition_id=operation.definition_id, source=operation.evidence,
                                 attributes=dict(element.attrib))
        closure.entry_step_note = record['entry_step_note']
        closure.steps = list(access.steps(context))
        closure.calls = list(access.calls(context))
        for call in closure.calls:
            if call.get('detail'):
                issue(call['step_note'], call['detail'])
        closure.routing_graph, switches = resolve_routing(access, context, sources, closure.steps, issue)
        mappings = dict((name, fqcn) for name, fqcn, _ in parse_channel_note(
            access.channel_evidence(context)['markdown'], context.channel))
        resolver = FormatResolver(access, context, sources, mappings, issue)
        closure.return_body_switches = resolver.resolve(element, switches)
        closure.format_roles, closure.formats = resolver.roles, resolver.nodes
        closure.context_chain = resolve_contexts(access, context, sources, element, issue)
        required = set(resolver.java_classes)
        for step in closure.steps:
            source = sources.xml(step.source)
            fqcn = source.get('implClass') or mappings.get('opStep')
            if not fqcn:
                issue(step.source.note, 'Missing implementation or consuming-channel opStep mapping',
                      ClosureStatus.BLOCKED_MISSING_IMPL_CLASS)
            else:
                required.add(fqcn)
        closure.java_origins, closure.external_dependencies = resolve_java_origins(
            access, context, sources, required, source_index, classpath_index, java_project, profile, issue)
        check_scoped_java_dependencies(access, context, sources, closure.java_origins, closure.external_dependencies,
                                       source_index, classpath_index, java_project, profile, issue)
        by_class = {origin['fqcn']: origin for origin in closure.java_origins if origin.get('status') == 'verified_source'}
        for step in closure.steps:
            element_step = sources.xml(step.source)
            fqcn = element_step.get('implClass') or mappings.get('opStep')
            for code in by_class.get(fqcn, {}).get('return_codes', {}):
                conditions = closure.routing_graph.get(step.source.note, {})
                if 'on' + code + 'Do' not in conditions and 'onOtherDo' not in conditions:
                    issue(step.source.note, 'Known return code lacks an evidenced route: ' + code)
        closure.context_fields = resolve_fields(closure.context_chain, closure.formats, closure.java_origins)
        if closure.external_dependencies:
            from runtime.composer_behavior_context import compact_behavior_evidence
            closure.external_dependencies, closure.composer_behavior_evidence = compact_behavior_evidence(
                closure.external_dependencies)
            compact = {(item['class_name'], item['origin']): item for item in closure.external_dependencies}
            for origin in closure.java_origins:
                if origin.get('evidence'):
                    evidence = origin['evidence']
                    origin['evidence'] = compact[(evidence['class_name'], evidence['origin'])]
    except (ValueError, OSError) as exc:
        issue(context.operation_id, 'Qualified closure evidence is unavailable: ' + str(exc))
    closure.source_revisions = dict(sources.used)
    return closure
