"""Build and validate exact implementing/supporting source evidence for component requests."""
from pathlib import Path


def component_sources(plan, group, bindings):
    """Read selected implementing sources and deduplicated declared supporting sources only."""
    sources = []
    origins = [(key, plan.components[bindings.get(key, key)].provenance) for key in group.members]
    for key, origin in origins:
        sources.append(dict(component_id=key, identity=origin['definition_id'], content_hash=origin['source_hash'],
                            content=Path(origin['source_file']).read_text(encoding='utf-8-sig')))
    seen = {source['identity'] for source in sources}
    for key, origin in origins:
        for supporting in origin.get('supporting_sources', []):
            if supporting['definition_id'] in seen:
                continue
            seen.add(supporting['definition_id'])
            sources.append(dict(component_id=key, identity=supporting['definition_id'],
                content_hash=supporting['source_hash'], role='supporting_source_only',
                content=Path(supporting['source_file']).read_text(encoding='utf-8-sig')))
    return sources


def validate_component_sources(plan, group, bindings, sources):
    """Reject missing, extra, repeated or altered original evidence before model execution."""
    expected = component_sources(plan, group, bindings)
    if not isinstance(sources, list) or any(not isinstance(source, dict) for source in sources):
        raise ValueError('Component request must contain each original source exactly once')
    keys = [(source.get('component_id'), source.get('identity')) for source in sources]
    if len(keys) != len(set(keys)) or set(keys) != {(source['component_id'], source['identity']) for source in expected}:
        raise ValueError('Component request must contain each implementing and declared supporting source exactly once')
    indexed = dict(zip(keys, sources))
    if any(indexed[(source['component_id'], source['identity'])] != source for source in expected):
        raise ValueError('Component request changed original source evidence')
