"""Publish read-only boundary analysis separately from native conversion acceptance."""

from tools.behavior_verification.boundary_contracts import boundary_contract
from tools.behavior_verification.java_tool import analyze_entries
from models.legacy_boundary_method import LegacyBoundaryMethod
from tools.behavior_verification.reachable_slice import read_reachable_slice
from tools.behavior_verification.parser_checklist import read_parser_checklist


def build_boundary_report(preparation, *, mappings=None, tool_jar=None, collect_checklists=True):
    """Identify entry methods and conservative slices; no behavioral pass is claimed."""
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
                scope = scopes.setdefault(boundary.source_manifest_hash,
                    dict(sources=list(unit_sources[boundary.unit_id].values()), boundaries=[]))
                scope['boundaries'].append(boundary)
    tool_hash = None
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
            for scope in scopes.values():
                for boundary in scope['boundaries']:
                    boundary.analysis_status = 'verification_incomplete'
                    boundary.legacy_method = None
                    boundary.issues.append(str(exc))
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
    return dict(schema_version='unit-boundaries-v1', run_id=preparation.get('run_id'),
        analysis_stage='boundary_reachability_and_checklist' if collect_checklists else 'boundary_reachability_only', analysis_tool_hash=tool_hash, acceptance_gate_enabled=False,
        checklist_counts=checklist_counts,
        verification_status='not_run', reachability_status=('not_run' if not slices else
            'analyzed' if analyzed == len(boundaries) and analyzed else 'verification_incomplete'),
        initialization_analysis_status='static_analysis_only' if slices else 'not_run', reachability_counts=reachability,
        counts=dict(total=len(boundaries), identified=identified,
            incomplete=len(boundaries) - identified),
        boundaries={key: value.model_dump(mode='json') for key, value in sorted(boundaries.items())})
