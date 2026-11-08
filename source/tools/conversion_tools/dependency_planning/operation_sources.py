"""Choose pinned/registered APIs before scheduling source operation dependencies."""
from runtime.operation_reuse.dependency_reuse import PublishedDependencies
from tools.conversion_tools.dependency_planning.required_scope import required_scope
from tools.conversion_tools.scoped_workflow.calls import published_boundaries
from tools.state_store_tools.service_api_uses import record_service_use


def operation_scope(conn, config, profile, graph, roots):
    """Resolve required work and pin discovered APIs without changing configured roots."""
    pins = published_boundaries(conn, config.run_id)
    roots = set(roots)
    with PublishedDependencies(profile) as available:
        def lookup(key):
            candidates = pins.get(key, [])
            if candidates:
                return candidates[0].contract if len(candidates) == 1 else None
            return available.lookup(key) if key not in roots else None
        scope = required_scope(graph, roots, lookup, excluded=getattr(config, 'exclude_operations', ()))
    for key, contract in scope.reused_services.items():
        if key not in pins:
            record_service_use(conn, config.run_id, contract, profile.deployment_environment, profile=profile)
    return scope
