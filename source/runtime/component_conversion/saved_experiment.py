"""Retain verified saved package names only inside an isolated facts experiment."""
from contextlib import contextmanager
from contextvars import ContextVar

_packages = ContextVar('saved_experiment_packages', default={})


def candidate_key(components):
    """Identify the same original implementation/configuration across policy fingerprints."""
    import json
    from tools.conversion_tools.scoped_reuse.fingerprints import digest
    values = []
    for node in components.values():
        if hasattr(node,'model_dump'):
            node = node.model_dump(mode='json')
        provenance = node['provenance']
        values.append(dict(kind=node['kind'],label=node['label'],configuration=node['configuration'],
            provenance={key:value for key,value in provenance.items() if key in
                {'definition_id','source_hash','source_definition_id','operation_identity','selector','resolved_implementation'}}))
    return digest(sorted(values,key=lambda item:json.dumps(item,sort_keys=True)))


def saved_package(profile, identity, default, components=None):
    """Keep the new policy revision while retaining immutable Java package names."""
    from runtime.behavior_conversion.verification_mode import facts_disabled
    if not facts_disabled(profile):
        return default
    packages = _packages.get()
    return packages.get(identity,packages.get(candidate_key(components),default) if components else default)


@contextmanager
def retain_packages(packages):
    """Scope package reuse to a single controlled continuation."""
    token = _packages.set(dict(packages))
    try:
        yield
    finally:
        _packages.reset(token)
