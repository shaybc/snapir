"""Validate source revisions, exact response coverage and native file identities."""
import hashlib
from pathlib import PurePosixPath
from tools.behavior_verification.boundary_contracts import boundary_contract, digest
from tools.behavior_verification.reachable_slice import _provenance


def candidate_files(files):
    """Accept canonical Java source paths; test code cannot serve as implementation evidence."""
    result, identities = {}, set()
    for file in files:
        path, content = (file['path'], file['content']) if isinstance(file, dict) else (file.path, file.content)
        parsed = PurePosixPath(path)
        if ('\\' in path or ':' in path or parsed.is_absolute() or '..' in parsed.parts or str(parsed) != path
            or not path.endswith('.java') or not path.startswith(('src/main/java/', 'src/test/java/'))):
            raise ValueError('Unsafe candidate Java path: ' + path)
        if path.casefold() in identities:
            raise ValueError('Duplicate candidate Java path: ' + path)
        result[path] = content
        identities.add(path.casefold())
    if not any(path.startswith('src/main/java/') for path in result):
        raise ValueError('Candidate has no main Java sources')
    return result


def candidate_digest(files):
    """Bind approvals to all candidate code, including its tests."""
    return digest({path: hashlib.sha256(content.encode('utf-8')).hexdigest() for path, content in sorted(files.items())})


def validate_revisions(unit, boundary, answers):
    """Reject stale sources/configuration/checklist and duplicate or missing answers."""
    current = boundary_contract(unit)
    if (current.unit_id, current.source_manifest_hash, current.configuration_hash) != (
        boundary.unit_id, boundary.source_manifest_hash, boundary.configuration_hash):
        raise ValueError('Boundary source or configuration revision changed')
    for field in ('unit_fingerprint', 'operation_identity', 'kind', 'implementation_class', 'method_name',
                  'parameter_contract', 'return_contract', 'inputs', 'observable_results', 'setup_class_roots', 'setup_bindings'):
        expected = getattr(current, field)
        if boundary.framework_boundaries:
            entry = boundary.framework_boundaries[0]
            expected = {'method_name': entry['method'], 'parameter_contract': entry['parameters'],
                        'return_contract': entry['returns']}.get(field, expected)
        else:
            from tools.framework_boundaries.inventory import current as framework_inventory
            if framework_inventory() and boundary.format_lifecycle and boundary.legacy_method:
                entry = boundary.format_lifecycle.invocations[-1]
                if entry.signature == boundary.legacy_method.signature:
                    expected = {'method_name': entry.method, 'parameter_contract': entry.parameters,
                                'return_contract': entry.returns}.get(field, expected)
        if expected != getattr(boundary, field):
            raise ValueError('Boundary contract/setup changed: ' + field)
    if (answers.unit_id, answers.source_manifest_hash, answers.configuration_hash) != (
        boundary.unit_id, boundary.source_manifest_hash, boundary.configuration_hash):
        raise ValueError('Checklist answers target a different source/configuration revision')
    checklist = boundary.parser_checklist
    if checklist is None or checklist.status != 'extracted' or (checklist.source_manifest_hash, checklist.configuration_hash) != (
        boundary.source_manifest_hash, boundary.configuration_hash):
        raise ValueError('An extracted, revision-bound parser checklist is required')
    ids = [item.id for item in checklist.items]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate parser checklist identity')
    graph = boundary.reachable_slice
    if graph is None or (graph.source_manifest_hash, graph.configuration_hash) != (boundary.source_manifest_hash, boundary.configuration_hash):
        raise ValueError('Parser checklist requires its revision-bound source graph')
    nodes, sources = {node.id: node for node in graph.nodes}, {source['identity']: source for source in unit['sources']}
    for item in checklist.items:
        _provenance(item.model_dump(), item.excerpt, sources)
        owner = nodes.get(item.code_node_id)
        if owner is None or (owner.source_identity, owner.source_hash) != (item.source_identity, item.source_hash):
            raise ValueError('Checklist item is outside its original source owner')
        start, end = (item.start_line, item.start_column), (item.end_line, item.end_column)
        if not (owner.start_line, owner.start_column) <= start <= end <= (owner.end_line, owner.end_column):
            raise ValueError('Checklist source range is outside its original source owner')
        span = ':'.join(map(str, (*start, *end)))
        expected = 'check-' + hashlib.sha256('\0'.join((owner.id, item.kind, item.detail, span)).encode()).hexdigest()
        if expected != item.id:
            raise ValueError('Checklist identity does not match its source span')
    actual = [answer.checklist_id for answer in answers.responses]
    errors = []
    for identity in sorted(set(ids) - set(actual)):
        errors.append(dict(checklist_id=identity, message='Missing checklist answer'))
    for identity in sorted(set(actual)):
        if identity not in ids:
            errors.append(dict(checklist_id=identity, message='Unknown checklist identity'))
        elif actual.count(identity) != 1:
            errors.append(dict(checklist_id=identity, message='Duplicate checklist answer'))
    return errors
