"""Project saved converter decisions into a graph without source scanning or inference."""
from models.conversion_graph import ConversionGraph
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def boundary_revision(report):
    """Fingerprint recorded boundary decisions without hashing or exporting source bodies."""
    decisions = {}
    fields = ('implementation_class', 'kind', 'method_name', 'parameter_contract', 'return_contract',
              'analysis_status', 'source_manifest_hash', 'configuration_hash', 'issues')
    for identity, boundary in report.get('boundaries', {}).items():
        item = {key: boundary.get(key) for key in fields}
        method = boundary.get('legacy_method') or boundary.get('framework_method') or {}
        item['method'] = {key: method.get(key) for key in ('declaring_class', 'signature', 'source_hash', 'jar_sha256')}
        decisions[identity] = item
    return digest(dict(decisions=decisions, tool=report.get('analysis_tool_hash'), classpath=report.get('analysis_classpath_hash')))


def graph_from_records(run_id, plan, boundaries, units, outcomes, *, validation=None, blockers=()):
    """Use exact plan relations, analyzer metadata and current outcomes; unknown stays unknown."""
    if hasattr(plan, 'model_dump'):
        plan = plan.model_dump(mode='json')
    graph = ConversionGraph(run_id=run_id, plan_fingerprint=plan.get('fingerprint'))
    graph.evidence = [dict(record='component_plan', fingerprint=plan.get('fingerprint')),
                      dict(record='boundary_report', analysis_tool_hash=boundaries.get('analysis_tool_hash'),
                           analysis_classpath_hash=boundaries.get('analysis_classpath_hash'), content_hash=boundary_revision(boundaries))]
    if 'groups' in outcomes:
        graph.evidence.append(dict(record='component_generation', content_hash=digest(outcomes)))
    components = plan.get('components', {})
    def node(identity, label, kind='class', **values):
        existing = graph.nodes.setdefault(identity, dict(id=identity, label=label, kind=kind,
            status='not_recorded', decision='not_recorded', issues=[], entry_points=[], evidence=[]))
        existing.update(values)
        return identity
    def edge(source, target, relation, evidence, **values):
        item = dict(id='edge-' + digest([source, target, relation, evidence]),
                    **{'from': source, 'to': target}, relation=relation, evidence=evidence, **values)
        if item not in graph.edges:
            graph.edges.append(item)
    for key, item in components.items():
        origin = item.get('provenance', {})
        node(key, item['label'], item['kind'], status=item.get('status', 'not_recorded'),
             decision='conversion_target' if item['kind'] in {'java_implementation', 'configured_step', 'format_composition'} else
                      'configuration_only' if item['kind'] == 'format_node' else origin.get('status', 'not_recorded'),
             issues=list(item.get('issues', [])), source_hash=origin.get('source_hash'),
             source_identity=origin.get('definition_id'),
             source_file=origin.get('source_file'), evidence=[dict(record='component_plan', pointer='/components/' + key)])
    for key, item in components.items():
        for target in item.get('dependencies', []):
            if target not in graph.nodes:
                node(target, target, 'missing_reference', issues=['Dependency target was not recorded'])
            reasons = item.get('dependency_reasons', {}).get(target, [])
            # These labels are emitted by the converter's configured graph builder, not guessed from names.
            containment = any(reason.startswith(('ordered child ', 'complete configured format', 'resolved refFmt definition ')) for reason in reasons)
            relation = 'contains' if containment else 'has_decorator' if any(reason.startswith('decorator index ') for reason in reasons) else 'uses'
            edge(key, target, relation,
                 dict(record='component_plan', component=key, dependency=target), reasons=reasons)
        for origin in item.get('provenance', {}).get('supporting_sources', []):
            target = 'source-' + digest([origin.get('definition_id'), origin.get('source_hash')])
            node(target, origin.get('fqcn') or origin.get('definition_id') or 'Supporting source',
                 decision='supporting_source_only', source_file=origin.get('source_file'), source_hash=origin.get('source_hash'))
            graph.nodes[target]['source_identity'] = origin.get('definition_id')
            edge(key, target, 'supporting_source', dict(record='component_plan', component=key,
                source_identity=origin.get('definition_id')))
    unit_roots = plan.get('unit_roots', {})
    graph.roots = list(dict.fromkeys(unit_roots.values()))
    def class_node(name, identity, record=None):
        record = record or {}
        scope = boundaries.get('diagnostic_structure', {}).get(identity, {}).get('resolution_scope') or boundaries.get('boundaries', {}).get(identity, {}).get('source_manifest_hash')
        candidates = [key for key, item in components.items() if item['label'] == name and
                      identity in item.get('unit_ids', []) and item['kind'] == 'java_implementation']
        if len(candidates) == 1:
            key = candidates[0]
        else:
            source = record.get('source_identity')
            matches = [key for key, item in graph.nodes.items() if source and item.get('source_identity') == source
                       and item.get('source_hash') == record.get('source_hash') and item.get('resolution_scope', scope) == scope]
            key = matches[0] if len(matches) == 1 else 'class-' + digest([name, record.get('source_hash'), record.get('source_identity'), scope])
        values = {field: record[field] for field in ('source_identity', 'source_hash', 'source_file') if record.get(field) is not None}
        if record.get('status'):
            values['structure_status'] = record['status']
        values['resolution_scope'] = scope
        node(key, name, **values)
        return key
    for identity, structure in boundaries.get('diagnostic_structure', {}).items():
        classes = structure.get('classes', [])
        for item in classes:
            class_node(item['name'], identity, item)
        for item in classes:
            source = class_node(item['name'], identity, item)
            for parent in item.get('parents', []):
                target = class_node(parent['name'], identity, next((value for value in classes if value['name'] == parent['name']), {}))
                edge(source, target, parent['relation'], dict(record='boundary_structure', unit_id=identity, owner=item['name']))
            for field in item.get('fields', []):
                target = class_node(field['type'], identity, next((value for value in classes if value['name'] == field['type']), {}))
                edge(source, target, 'has_field', dict(record='boundary_structure', unit_id=identity,
                    owner=item['name'], field=field['name']))
        if structure.get('issues'):
            graph.issues.extend(structure['issues'])
        for issue in structure.get('issue_records', []):
            if not issue.get('owner'):
                continue
            source = class_node(issue['owner'], identity, next((item for item in classes if item['name'] == issue['owner']), {}))
            target = 'missing-' + digest([identity, issue])
            node(target, issue['message'], 'missing_reference', status='not_found', decision='diagnostic_only')
            edge(source, target, 'unresolved_reference', dict(record='boundary_structure', unit_id=identity, **issue))
    directions = dict(response_format='format', request_unformat='unformat', configured_step='execute')
    for identity, boundary in boundaries.get('boundaries', {}).items():
        selected = boundary.get('implementation_class')
        root = unit_roots.get(identity)
        if not selected:
            if root in graph.nodes:
                graph.nodes[root]['issues'].extend(boundary.get('issues', []))
                graph.nodes[root]['entry_points'].append(dict(unit_id=identity, role='selected',
                    direction=directions.get(boundary.get('kind'), 'not_recorded'),
                    selected_class=None, status=boundary.get('analysis_status', 'not_recorded'),
                    expected_signature=boundary.get('return_contract', '') + ' ' + boundary.get('method_name', '?') +
                        '(' + ', '.join(boundary.get('parameter_contract', [])) + ')', issues=boundary.get('issues', [])))
            continue
        owner = class_node(selected, identity)
        reachable = boundary.get('reachable_slice') or {}
        code_nodes = {item['id']: item for item in reachable.get('nodes', [])}
        for call in reachable.get('edges', []):
            caller = code_nodes.get(call.get('from_id'))
            source = class_node(caller['declaring_class'], identity, caller) if caller else owner
            for candidate in call.get('candidates', []):
                target_record = code_nodes.get(candidate)
                if target_record:
                    target = class_node(target_record['declaring_class'], identity, target_record)
                else:
                    target = 'reference-' + digest([identity, candidate])
                    node(target, call.get('declared_target') or candidate, 'external_reference',
                         status='unbounded' if call.get('unbounded') else 'not_recorded', issues=[call.get('reason', '')])
                if source != target:
                    edge(source, target, 'uses', dict(record='reachable_slice', unit_id=identity, edge_id=call['id']),
                         uncertain=call.get('uncertain'), unbounded=call.get('unbounded'), reason=call.get('reason'))
        if root and root in graph.nodes and root != owner:
            edge(root, owner, 'uses', dict(record='boundary', unit_id=identity))
        method = boundary.get('legacy_method') or boundary.get('framework_method')
        entry = dict(unit_id=identity, direction=directions.get(boundary.get('kind'), boundary.get('kind')),
            selected_class=selected, status=boundary.get('analysis_status', 'not_recorded'),
            source_manifest_hash=boundary.get('source_manifest_hash'), configuration_hash=boundary.get('configuration_hash'),
            expected_signature=boundary.get('return_contract', '') + ' ' + boundary.get('method_name', '?') +
                '(' + ', '.join(boundary.get('parameter_contract', [])) + ')',
            issues=boundary.get('issues', []), evidence=dict(record='boundary', unit_id=identity))
        if method:
            entry.update(declaring_class=method['declaring_class'], signature=method['signature'],
                         return_type=method.get('return_type'), source_hash=method.get('source_hash'))
            declaring = class_node(method['declaring_class'], identity, method)
            if boundary.get('framework_method'):
                graph.nodes[declaring].update(decision='framework_boundary', jar_path=method['jar_path'], jar_sha256=method['jar_sha256'])
            if declaring != owner:
                edge(owner, declaring, 'entry_declared_by', entry['evidence'], direction=entry['direction'])
            graph.nodes[declaring]['entry_points'].append(dict(entry, role='declares'))
        graph.nodes[owner]['entry_points'].append(dict(entry, role='selected'))
        if root in graph.nodes and root != owner:
            graph.nodes[root]['entry_points'].append(dict(entry, role='selected'))
    for group, outcome in outcomes.get('groups', {}).items():
        group_record = next((item for item in plan.get('groups', []) if item['group_id'] == group), {})
        for key in outcome.get('members', group_record.get('members', [])):
            if key not in graph.nodes:
                continue
            graph.nodes[key].update(status=outcome['status'], reused=outcome.get('reused', False),
                reason=outcome.get('reason'), validation_scope=outcome.get('validation_scope'))
            graph.nodes[key]['evidence'].append(dict(record='component_generation', group_id=group))
            if outcome['status'] == 'component_validated':
                detail = (validation or {}).get(key, {})
                if detail.get('plan_fingerprint') == plan.get('fingerprint'):
                    graph.nodes[key]['comparisons'] = detail.get('comparisons', {})
                    for api in detail.get('native_apis', []):
                        target = 'native-' + digest([api, detail.get('result_revision')])
                        node(target, api, 'native_class', status='build_and_tests_passed',
                             evidence=[detail['evidence']])
                        edge(key, target, 'converted_to', detail['evidence'])
    for blocker in blockers:
        if blocker.get('plan_fingerprint') != plan.get('fingerprint'):
            continue
        current = outcomes.get('groups', {}).get(blocker['group_id'], {})
        if current.get('reason') != blocker['reason']:
            continue
        dependencies = next((item['members'] for item in plan.get('groups', [])
                             if item['group_id'] == blocker['dependency_group']), [])
        for source in current.get('members', []):
            for target in dependencies:
                edge(source, target, 'blocked_by', dict(record='converter_blocker', **blocker))
    if outcomes.get('fatal_error'):
        failure = node('fatal-' + digest(outcomes['fatal_error']), 'Converter failure', 'converter_error',
                       status='failed', reason=outcomes['fatal_error'])
        for outcome in outcomes.get('groups', {}).values():
            if outcome.get('status') == 'running':
                for key in outcome.get('members', []):
                    if key in graph.nodes:
                        edge(key, failure, 'blocked_by', dict(record='component_generation', field='fatal_error'))
        graph.roots.append(failure)
    operations = {}
    for key, item in components.items():
        if key not in unit_roots.values():
            continue
        for operation in item.get('operations', []):
            operations.setdefault(operation, set()).add(key)
    for label, children in operations.items():
        identity = node('operation-' + digest(label), label, 'operation', status='not_recorded',
                        issues=['Operation acceptance is separate from component validation'])
        for child in sorted(children - {None}):
            if child in graph.nodes:
                edge(identity, child, 'contains', dict(record='component_plan', operation=label))
        graph.roots.append(identity)
    graph.issues.extend(['Relationships absent from converter records are not reconstructed.',
                         'Uses and field references do not establish ownership or runtime execution.'])
    graph.issues = list(dict.fromkeys(graph.issues))
    graph.snapshot_id = digest(graph.model_dump(mode='json', exclude={'snapshot_id', 'recorded_at'}))
    return ConversionGraph.model_validate(graph.model_dump())
