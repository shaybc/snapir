"""Exercise the real component authorization gate with implementing and supporting sources."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from runtime.component_conversion.requests import build_component_request
from runtime.component_conversion.scope import component_execution, require_component_task
from runtime.component_conversion.source_evidence import component_sources, validate_component_sources
from tools.conversion_tools.component_graph import build_component_plan
from tools.conversion_tools.component_identity import component_group
from test_component_graph import origin, operation, step


@pytest.fixture
def source_case(tmp_path, monkeypatch):
    originals = [origin('example.Work', ['example.Context']), origin('example.Context')]
    for record, text in originals:
        path = tmp_path / (record['fqcn'].split('.')[-1] + '.java')
        path.write_text(text, encoding='utf-8')
        record['source_file'] = str(path)
    unit = step()
    operations = {'XML/Test': operation([unit], originals)}
    plan = build_component_plan(operations)
    node = next(node for node in plan.components.values() if node.kind == 'java_implementation')
    boundary = dict(reachable_slice=dict(nodes=[dict(source_identity=node.provenance['definition_id'],
        source_hash=node.provenance['source_hash'], kind='method', signature='example.Work.execute()')]),
        parser_checklist=dict(items=[]))
    profile = PipelineConfiguration(java_version=25, scoped_native_mode='component_first_v1',
                                    conversion_strategy='behavior_units')
    config = SimpleNamespace(run_id='source-authorization')
    conn = object()
    monkeypatch.setattr('runtime.component_conversion.scope.validate_checkpoints', lambda *a: None)
    return conn, config, profile, dict(operations=operations, component_plan=plan.model_dump(mode='json')), plan, node, dict(
        boundaries={unit['unit_id']: boundary}, analysis_tool_hash='parser'), unit


@pytest.mark.parametrize('configured', [False, True])
def test_real_gate_accepts_implementing_and_supporting_sources(source_case, configured):
    conn, config, profile, preparation, plan, node, boundaries, unit = source_case
    group = component_group(plan, plan.unit_roots[unit['unit_id']] if configured else node.component_id)
    request, _ = build_component_request(plan, group, boundaries, [], profile, units={unit['unit_id']: unit})
    assert len(request['sources']) == 2
    with component_execution(conn, config, profile, None, preparation, include_steps=True):
        require_component_task(conn, config, profile, group.group_id, request)
        # Source ordering is not identity; both sources are still checked exactly.
        reordered = deepcopy(request)
        reordered['sources'].reverse()
        require_component_task(conn, config, profile, group.group_id, reordered)


@pytest.mark.parametrize('problem', ['missing_main', 'missing_support', 'duplicate_main', 'duplicate_support',
    'extra', 'content', 'hash', 'role', 'owner', 'identity'])
def test_real_gate_rejects_missing_duplicate_extra_or_changed_sources(source_case, problem):
    conn, config, profile, preparation, plan, node, boundaries, unit = source_case
    group = component_group(plan, node.component_id)
    request, _ = build_component_request(plan, group, boundaries, [], profile)
    sources = request['sources']
    if problem == 'missing_main': sources.pop(0)
    elif problem == 'missing_support': sources.pop(1)
    elif problem == 'duplicate_main': sources.append(deepcopy(sources[0]))
    elif problem == 'duplicate_support': sources.append(deepcopy(sources[1]))
    elif problem == 'extra': sources.append(dict(sources[1], identity='unrelated-source'))
    else:
        field = dict(content='content', hash='content_hash', role='role', owner='component_id', identity='identity')[problem]
        sources[1][field] = 'changed'
    with component_execution(conn, config, profile, None, preparation, include_steps=True):
        with pytest.raises(ValueError, match='source'):
            require_component_task(conn, config, profile, group.group_id, request)


def test_single_source_and_shared_support_remain_unique(source_case):
    _, _, _, _, plan, node, _, _ = source_case
    group = component_group(plan, node.component_id)
    sources = component_sources(plan, group, {})
    node.provenance['supporting_sources'].append(deepcopy(node.provenance['supporting_sources'][0]))
    assert component_sources(plan, group, {}) == sources
    validate_component_sources(plan, group, {}, sources)
    node.provenance.pop('supporting_sources')
    main_only = component_sources(plan, group, {})
    assert len(main_only) == 1
    validate_component_sources(plan, group, {}, main_only)


@pytest.mark.parametrize('newline,bom', [('\n',False),('\r\n',False),('\r\n',True)])
def test_source_catalog_preserves_raw_hash_for_main_and_support(tmp_path,newline,bom):
    import hashlib
    from runtime.behavior_conversion.metadata_checklist_evidence import source_catalog
    origins=[]
    for name in ('Work','Context'):
        raw=(('\ufeff' if bom else '')+'class '+name+' {'+newline+'}'+newline).encode('utf-8')
        path=tmp_path/(name+'.java');path.write_bytes(raw)
        origins.append(dict(definition_id=name,source_file=str(path),source_hash=hashlib.sha256(raw).hexdigest()))
    origins[0]['supporting_sources']=[origins[1]]
    plan=SimpleNamespace(components={'work':SimpleNamespace(provenance=origins[0])})
    group=SimpleNamespace(members=['work'])
    sources=component_sources(plan,group,{})
    assert all(hashlib.sha256(s['content'].encode('utf-8')).hexdigest()==s['content_hash'] for s in sources)
    assert len(source_catalog(dict(sources=sources),{},{}))==2
    validate_component_sources(plan,group,{},sources)
    changed=deepcopy(sources);changed[1]['content']+='// altered'
    with pytest.raises(ValueError,match='Original evidence hash changed'):
        source_catalog(dict(sources=changed),{},{})
    with pytest.raises(ValueError,match='changed original source evidence'):
        validate_component_sources(plan,group,{},changed)
