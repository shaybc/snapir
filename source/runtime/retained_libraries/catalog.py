"""Bind original verified library candidates to one generation without changing user profiles."""

from contextlib import contextmanager
from contextvars import ContextVar
from models.retained_library import RetainedLibrary

_active = ContextVar('retained_library_candidates', default=None)


def record_libraries(records):
    """Deduplicate by artifact identity while preserving required class ownership."""
    result = {}
    for record in records:
        data = record.get('library')
        if not data:
            continue
        item = RetainedLibrary.model_validate(data)
        key = item.dependency.coordinates
        if key in result:
            previous = result[key]
            if previous.sha256 != item.sha256:
                raise ValueError('Retained dependency has conflicting original bytes: ' + key)
            previous.dependency.required_classes = sorted(set(previous.dependency.required_classes + item.dependency.required_classes))
        else:
            result[key] = item
    return [result[key].model_dump(mode='json') for key in sorted(result)]


def plan_libraries(plan, group):
    """Read only the selected group's supporting dependency records, not unrelated operations."""
    pending, seen, records = list(group.members), set(), []
    while pending:
        key = pending.pop()
        if key in seen:
            continue
        seen.add(key)
        node = plan.components[key]
        if node.provenance.get('evidence'):
            records.append(node.provenance['evidence'])
        pending.extend(node.dependencies)
    return record_libraries(records)


def current():
    """Return the profile and candidates of the owning generation, if any."""
    return _active.get()


@contextmanager
def library_scope(profile, payload):
    """Expose trusted candidates as optional dependencies to code and metadata stages."""
    records = list(payload.get('external_dependencies', []))
    for key in ('unit', 'configured_unit', 'configured_format'):
        records.extend((payload.get(key) or {}).get('external_dependencies', []))
    libraries = list(payload.get('retained_libraries', [])) + record_libraries(records)
    by_coordinate = {}
    inherited = current()
    if inherited:
        libraries = list(inherited[1].values()) + libraries
    for value in libraries:
        item = RetainedLibrary.model_validate(value)
        key = item.dependency.coordinates
        if key in by_coordinate and by_coordinate[key]['sha256'] != item.sha256:
            raise ValueError('Retained library scope has competing artifacts: ' + key)
        if key in by_coordinate:
            item.dependency.required_classes = sorted(set(item.dependency.required_classes + by_coordinate[key]['dependency']['required_classes']))
        by_coordinate[key] = item.model_dump(mode='json')
    token = _active.set((profile, by_coordinate))
    try:
        if by_coordinate:
            payload['retained_libraries'] = [by_coordinate[key] for key in sorted(by_coordinate)]
            known = list(payload.get('known_dependencies', []))
            existing = {(item['group_id'], item['artifact_id']) for item in known}
            for item in by_coordinate.values():
                dependency = item['dependency']
                if (dependency['group_id'], dependency['artifact_id']) not in existing:
                    known.append(dependency)
            payload['known_dependencies'] = known
        yield
    finally:
        _active.reset(token)


def approved_ibm_dependency(dependency):
    """Only application-verified original IBM artifacts may cross the ordinary client boundary."""
    scope = current()
    if not scope:
        return False
    value = scope[1].get(dependency.coordinates)
    return bool(value and value['ibm'] and set(dependency.required_classes) <= set(value['dependency']['required_classes']))


def allowed_client_classes(allowed):
    """Add exact client APIs from verified candidates; no package wildcard approval."""
    scope = current()
    if scope:
        from runtime.retained_libraries.artifacts import verify_library
        for item in scope[1].values():
            if item['ibm']:
                verify_library(item, scope[0])
    return tuple(sorted(set(allowed) | {name for item in scope[1].values() if item['ibm']
                                      for name in item['dependency']['required_classes']})) if scope else allowed
