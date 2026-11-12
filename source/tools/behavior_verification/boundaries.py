"""Publish read-only boundary analysis separately from native conversion acceptance."""

from tools.behavior_verification.boundary_contracts import boundary_contract
from tools.behavior_verification.java_tool import analyze_entries
from models.legacy_boundary_method import LegacyBoundaryMethod
from tools.behavior_verification.reachable_slice import read_reachable_slice
from tools.behavior_verification.parser_checklist import read_parser_checklist


def build_boundary_report(preparation, *, mappings=None, tool_jar=None, collect_checklists=True, classpath_index=None, original_classpath=()):
    """Identify entry methods and conservative slices; no behavioral pass is claimed."""
    from tools.behavior_verification.format_lifecycle import expanded_preparation, read_lifecycle
    preparation, basic_ids = expanded_preparation(preparation)
    boundaries, scopes, unit_sources, source_paths = {}, {}, {}, {}
    for operation, item in sorted(preparation.get('operations', {}).items()):
        origins = {origin['definition_id']: origin['source_file']
                   for origin in item.get('behavior_request', {}).get('java_origins', [])
                   if origin.get('status') == 'verified_source'}
        for unit in item.get('units', []):
            if unit['unit_id'] in boundaries:
                raise ValueError('Boundary report contains a duplicate configured unit: ' + unit['unit_id'])
            boundary = boundary_contract(unit, (mappings or {}).get(operation, {}))
            boundaries[boundary.unit_id] = boundary
            unit_sources[boundary.unit_id] = {source['identity']: source for source in unit['sources']}
            if len(unit_sources[boundary.unit_id]) != len(unit['sources']):
                for source in unit['sources']:
                    if unit_sources[boundary.unit_id][source['identity']] != source:
                        raise ValueError('Conflicting unit source evidence identity: ' + source['identity'])
            source_paths[boundary.unit_id] = origins
            if not boundary.issues:
                from tools.behavior_verification.boundary_classpath import project_context
                try:
                    context = project_context(unit, boundary,
                        item.get('behavior_request', {}).get('java_origins', []), classpath_index,
                        **({'original_classpath': original_classpath} if original_classpath else {}))
                except ValueError as error:
                    boundary.issues.append(str(error))
                    continue
                key = boundary.source_manifest_hash + ':' + context['fingerprint'] if context else boundary.source_manifest_hash
                scope = scopes.setdefault(key,
                    dict(sources=list(unit_sources[boundary.unit_id].values()), boundaries=[], classpath=context))
                scope['boundaries'].append(boundary)
    tool_hash = None
    analysis_failures = []
    if scopes:
        try:
            analysis, tool_hash = (analyze_entries(scopes, tool_jar) if collect_checklists else
                                   analyze_entries(scopes, tool_jar, collect_checklists=False))
            returned = set()
            for entry in analysis.findall('entry'):
                identity = entry.get('id')
                if identity not in boundaries or identity in returned:
                    raise ValueError('Analysis returned an unexpected or duplicate unit identity')
                returned.add(identity)
                boundary = boundaries[identity]
                issues = [node.get('message') for node in entry.findall('issue')]
                framework = entry.find('framework-boundary')
                if framework is not None and not issues:
                    from tools.framework_boundaries.inventory import owner
                    library = owner(framework.get('declaring_class'))
                    if library is None or library['sha256'] != framework.get('sha256') or library['path'] != framework.get('path'):
                        raise ValueError('Unverified framework boundary ownership')
                    boundary.framework_boundaries = [dict(framework.attrib,
                        parameters=[item.get('type') for item in framework.findall('parameter')])]
                    boundary.analysis_status = 'identified'
                    boundary.method_name = framework.get('method')
                    boundary.return_contract = framework.get('returns')
                    boundary.parameter_contract = boundary.framework_boundaries[0]['parameters']
                    boundary.reachable_slice = read_reachable_slice(entry.find('reachability'), boundary,
                        unit_sources[identity], source_paths[identity])
                    if collect_checklists and not unit_sources[identity]:
                        from models.unit_parser_checklist import UnitParserChecklist
                        evidence = dict(source_manifest_hash=boundary.source_manifest_hash, configuration_hash=boundary.configuration_hash,
                            status='extracted', reachability_status='not_run')
                        boundary.parser_checklist = UnitParserChecklist(**evidence)
                        boundary.basic_parser_checklist = UnitParserChecklist(**evidence, fact_scope='basic_element')
                    elif collect_checklists:
                        boundary.parser_checklist = read_parser_checklist(entry.find('checklist'), boundary,
                            unit_sources[identity], source_paths[identity])
                        boundary.basic_parser_checklist = read_parser_checklist(entry.find('basic-checklist'), boundary,
                            unit_sources[identity], source_paths[identity], fact_scope='basic_element')
                    continue
                methods = entry.findall('method')
                if issues or len(methods) != 1:
                    boundary.issues.extend(issues or ['Entry method has no unique source implementation'])
                    continue
                method = methods[0]
                source = unit_sources[identity].get(method.get('source_identity'))
                excerpt = method.findtext('excerpt', '')
                if source is None or method.get('source_hash') != source['content_hash'] or not excerpt.strip() or excerpt not in source['content']:
                    raise ValueError('Boundary method is outside its supplied source revision')
                boundary.legacy_method = LegacyBoundaryMethod(**method.attrib, excerpt=excerpt,
                    source_file=source_paths[identity].get(source['identity']))
                boundary.format_lifecycle = read_lifecycle(entry.find('lifecycle'), unit_sources[identity])
                if boundary.format_lifecycle:
                    primary = boundary.format_lifecycle.invocations[-1]
                    boundary.method_name = primary.method
                    boundary.parameter_contract = primary.parameters
                    boundary.return_contract = primary.returns
                boundary.analysis_status = 'identified'
                boundary.reachable_slice = read_reachable_slice(entry.find('reachability'), boundary,
                    unit_sources[identity], source_paths[identity])
                if collect_checklists:
                    boundary.parser_checklist = read_parser_checklist(entry.find('checklist'), boundary,
                        unit_sources[identity], source_paths[identity])
                    boundary.basic_parser_checklist = read_parser_checklist(entry.find('basic-checklist'), boundary,
                        unit_sources[identity], source_paths[identity],fact_scope='basic_element')
            for scope in scopes.values():
                for boundary in scope['boundaries']:
                    if boundary.unit_id not in returned:
                        boundary.issues.append('Analysis returned no entry for this unit')
        except (OSError, ValueError) as exc:
            from tools.conversion_tools.scoped_reuse.fingerprints import digest
            failure = dict(getattr(exc, 'details', dict(kind='boundary_analysis_error', message=str(exc))))
            failure['affected_units'] = sorted(boundary.unit_id for scope in scopes.values() for boundary in scope['boundaries'])
            failure['id'] = 'boundary-analysis-' + digest(failure)[:20]
            analysis_failures.append(failure)
            for scope in scopes.values():
                for boundary in scope['boundaries']:
                    boundary.analysis_failure_id = failure['id']
                    boundary.analysis_status = 'verification_incomplete'
                    boundary.legacy_method = None
                    boundary.issues.append(str(exc))
    basic_boundaries = {key: boundaries.pop(key).model_dump(mode='json') for key in sorted(basic_ids)}
    identified = sum(item.analysis_status == 'identified' for item in boundaries.values())
    slices = [item.reachable_slice for item in boundaries.values() if item.reachable_slice is not None]
    analyzed = sum(item.status == 'analyzed' for item in slices)
    reachability = dict(total=len(boundaries), analyzed=analyzed,
        incomplete=sum(item.status == 'verification_incomplete' for item in slices),
        not_run=len(boundaries) - len(slices) + sum(item.status == 'not_run' for item in slices),
        uncertain_edges=sum(edge.uncertain for item in slices for edge in item.edges),
        unbounded_edges=sum(edge.unbounded for item in slices for edge in item.edges))
    checklists = [item.parser_checklist for item in boundaries.values() if item.parser_checklist is not None]
    checklist_counts = dict(total=len(boundaries), extracted=sum(item.status == 'extracted' for item in checklists),
        incomplete=sum(item.status == 'verification_incomplete' for item in checklists),
        not_run=len(boundaries) - len(checklists), items=sum(len(item.items) for item in checklists))
    from tools.conversion_tools.scoped_reuse.fingerprints import digest
    classpaths = {key: scope['classpath'] for key, scope in scopes.items() if scope.get('classpath')}
    return dict(**({'analysis_failures': analysis_failures} if analysis_failures else {}), schema_version='unit-boundaries-v1', run_id=preparation.get('run_id'), basic_boundaries=basic_boundaries,
        analysis_classpaths=classpaths, analysis_classpath_hash=digest(classpaths) if classpaths else None,
        analysis_stage='boundary_reachability_and_checklist' if collect_checklists else 'boundary_reachability_only', analysis_tool_hash=tool_hash, acceptance_gate_enabled=False,
        checklist_counts=checklist_counts,
        verification_status='not_run', reachability_status=('not_run' if not slices else
            'analyzed' if analyzed == len(boundaries) and analyzed else 'verification_incomplete'),
        initialization_analysis_status='static_analysis_only' if slices else 'not_run', reachability_counts=reachability,
        counts=dict(total=len(boundaries), identified=identified,
            incomplete=len(boundaries) - identified),
        boundaries={key: value.model_dump(mode='json') for key, value in sorted(boundaries.items())})
