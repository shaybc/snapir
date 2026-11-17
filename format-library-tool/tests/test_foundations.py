"""Synthetic foundation handoffs prove approval reuse and source ownership without live AI."""
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_tool import config, evidence, response
from format_library.files import read_json, write_json, digest, file_hash
from format_library.planning import build_plan
from format_library.workspaces import prepare
from format_library.prompts import build_request
from format_library.approval import approve
from format_library.generated_files import extract


def foundation_evidence(config):
    result = evidence(config, {
        'example.FormatElement': [], 'example.FieldFormat': ['example.FormatElement'],
        'example.Utility': [], 'example.StringFormat': ['example.FieldFormat'],
        'example.DateFormat': ['example.FieldFormat']})
    for name in ('example.FormatElement', 'example.FieldFormat'):
        result['classes'][name].update(abstract=True, framework=True)
    result['classes']['example.Utility']['kind'] = 'support'
    for name in ('example.StringFormat', 'example.DateFormat'):
        result['classes'][name]['ancestors'] = ['example.FieldFormat', 'example.FormatElement']
    result['foundation_groups'] = {'fields': ['example.FormatElement', 'example.FieldFormat', 'example.Utility']}
    config['foundation_groups'] = result['foundation_groups']
    return result


def foundation_response(manifest, split=False):
    base = manifest['native_package'] + '.NativeFieldBase'
    components = [dict(native_class=base, covered_original_classes=manifest['members'],
        kind='abstract_class', constructors=['protected NativeFieldBase(java.util.Map<String,String> attributes)'],
        methods=['public XmlElement format(Object value, FormatContext context)'],
        hooks=['protected abstract String formatValue(Object value)'],
        integration_notes='Subclasses override formatValue; common defaults and delegation belong to this base.')]
    if split:
        components.append(dict(native_class=manifest['native_package'] + '.SettingsSupport',
            covered_original_classes=['example.Utility'], kind='class', constructors=[],
            methods=['public static String setting(String name)'], hooks=[], integration_notes='Native settings helper.'))
    files = [dict(path='src/main/java/' + item['native_class'].replace('.', '/') + '.java',
        content='package ' + manifest['native_package'] + '; public abstract class ' +
                item['native_class'].rsplit('.', 1)[-1] + ' {}') for item in components]
    return json.dumps(dict(status='generated', files=files, components=components, dependencies=[], notes=[]))


def generate(config, folder, *, attempt='one', foundation=False, split=False):
    manifest = read_json(folder / 'component.json')
    request = build_request(config, folder, manifest)
    target = folder / 'attempts' / attempt; target.mkdir()
    payload = foundation_response(manifest, split) if foundation else response(manifest)
    return extract(folder, manifest, payload, request, target), request


def test_shared_bases_first_then_native_reuse_with_smaller_request(config):
    plan = build_plan(foundation_evidence(config))
    assert [item['stage'] for item in plan['groups']] == ['foundation', 'component', 'component']
    assert not any(item['blockers'] for item in plan['groups'])
    folders = prepare(config, plan, ['StringFormat'])
    foundation, formatter = folders
    assert foundation.parent.name == 'foundations'
    assert formatter.parent.name == 'components'
    with pytest.raises(ValueError, match='human approval'):
        build_request(config, formatter, read_json(formatter / 'component.json'))
    _, request = generate(config, foundation, foundation=True, split=True)
    assert request['stage'] == 'foundation'
    assert 'may be abstract' in request['prompt']
    approved = approve(config, foundation, reviewed=True)
    record = read_json(approved / 'approval.json')
    assert record['stage'] == 'foundation' and not record['verified']
    _, request = generate(config, formatter)
    assert len(request['omitted_original_sources']) == 3
    original_attachments = [path for path in request['attachments'] if path.startswith('sources/')]
    assert len(original_attachments) == 1 and original_attachments[0].endswith('StringFormat.java')
    assert len(list((formatter / 'sources').rglob('*.java'))) == 4
    assert any('NativeFieldBase.java' in path for path in request['attachments'])
    assert 'formatValue' in request['prompt']
    assert 'Implement only the remaining differences' in request['prompt']
    assert 'DateFormat.java' not in '\n'.join(request['attachments'])
    approve(config, formatter, reviewed=True)


def test_foundation_change_invalidates_unpublished_dependent_candidate(config):
    folders = prepare(config, build_plan(foundation_evidence(config)), ['StringFormat'])
    foundation, formatter = folders
    candidate, _ = generate(config, foundation, foundation=True)
    first = approve(config, foundation, reviewed=True)
    generate(config, formatter)
    java = next(candidate.rglob('*.java'))
    java.write_text(java.read_text() + '\n// reviewed change')
    second = approve(config, foundation, reviewed=True)
    assert first != second and first.exists()
    with pytest.raises(ValueError, match='approvals changed'):
        approve(config, formatter, reviewed=True)
    _, refreshed = generate(config, formatter, attempt='two')
    assert refreshed['prerequisites'][0]['revision'] == second.name


def test_source_and_policy_mismatches_block_reuse(config):
    discovery = foundation_evidence(config)
    foundation, formatter = prepare(config, build_plan(discovery), ['StringFormat'])
    generate(config, foundation, foundation=True)
    approved = approve(config, foundation, reviewed=True)
    # Create another preparation from changed original evidence, preserving old artifacts.
    original = Path(discovery['classes']['example.FieldFormat']['file'])
    original.write_text(original.read_text() + '\n// new original revision')
    discovery['hashes'][str(original)] = file_hash(original)
    config['output_root'] += '-new'
    _, current = prepare(config, build_plan(discovery), ['StringFormat'])
    with pytest.raises(ValueError, match='source revision differs'):
        build_request(config, current, read_json(current / 'component.json'))
    assert approved.exists()
    # A legacy approval cannot satisfy a v2 prepared prerequisite even if its file bytes match.
    record = read_json(approved / 'approval.json')
    record.pop('policy')
    record.pop('revision')
    revision = digest(record); record['revision'] = revision
    import shutil
    legacy = approved.parent / revision
    shutil.copytree(approved, legacy)
    write_json(legacy / 'approval.json', record)
    index = Path(config['approved_library_root']) / 'index.json'
    write_json(index, {record['id']: revision})
    with pytest.raises(ValueError, match='policy/stage'):
        build_request(config, formatter, read_json(formatter / 'component.json'))


def test_same_file_originals_are_not_silently_removed(config):
    discovery = foundation_evidence(config)
    child = discovery['classes']['example.StringFormat']
    child['file'] = discovery['classes']['example.FieldFormat']['file']
    foundation, formatter = prepare(config, build_plan(discovery), ['StringFormat'])
    generate(config, foundation, foundation=True)
    approve(config, foundation, reviewed=True)
    request = build_request(config, formatter, read_json(formatter / 'component.json'))
    assert request['mixed_original_sources']
    assert any(path.endswith('FieldFormat.java') for path in request['attachments'])
    assert 'Covered declarations are evidence only' in request['prompt']


def test_missing_framework_source_is_a_blocker_not_a_decompilation(config):
    discovery = evidence(config, {'example.StringFormat': ['vendor.Base']})
    discovery['classes']['example.StringFormat']['ancestors'] = ['vendor.Base']
    discovery['foundation_groups'] = {'binary_base': ['vendor.Base']}
    config['foundation_groups'] = discovery['foundation_groups']
    plan = build_plan(discovery)
    assert plan['groups'][0]['stage'] == 'foundation'
    assert any('requires source' in reason for reason in plan['groups'][0]['blockers'])
    foundation = prepare(config, plan, stage='foundation')[0]
    with pytest.raises(ValueError, match='requires source'):
        build_request(config, foundation, read_json(foundation / 'component.json'))


def test_foundation_stage_selection_and_export_validation(config):
    plan = build_plan(foundation_evidence(config))
    folders = prepare(config, plan, stage='foundation')
    assert len(folders) == 1
    manifest = read_json(folders[0] / 'component.json')
    payload = json.loads(foundation_response(manifest))
    payload['components'][0]['covered_original_classes'] = ['wrong.Class']
    with pytest.raises(ValueError, match='outside'):
        extract(folders[0], manifest, json.dumps(payload), dict(prerequisites=[]), folders[0] / 'attempts/bad')
    with pytest.raises(ValueError, match='older artifacts'):
        prepare(config, dict(plan, policy='legacy'))


def test_frozen_foundation_files_cannot_be_returned_by_concrete_conversion(config):
    foundation, formatter = prepare(config, build_plan(foundation_evidence(config)), ['StringFormat'])
    generate(config, foundation, foundation=True)
    artifact = approve(config, foundation, reviewed=True)
    manifest = read_json(formatter / 'component.json')
    request = build_request(config, formatter, manifest)
    payload = json.loads(response(manifest))
    approval = read_json(artifact / 'approval.json')
    frozen = approval['files'][0]
    payload['files'].append(dict(path=frozen['path'], content=(artifact / frozen['path']).read_text()))
    with pytest.raises(ValueError, match='must not regenerate'):
        extract(formatter, manifest, json.dumps(payload), request, formatter / 'attempts/overwrite')


def test_configuration_changes_require_new_discovery_and_preparation(config):
    plan = build_plan(foundation_evidence(config))
    foundation = prepare(config, plan, stage='foundation')[0]
    config['foundation_groups'] = {'different': ['example.FieldFormat']}
    with pytest.raises(ValueError, match='run discover again'):
        prepare(config, plan)
    with pytest.raises(ValueError, match='configuration differs'):
        build_request(config, foundation, read_json(foundation / 'component.json'))


def test_cross_stage_cycles_are_blocked_for_boundary_review(config):
    discovery = foundation_evidence(config)
    discovery['classes']['example.FieldFormat']['dependencies'].append('example.StringFormat')
    plan = build_plan(discovery)
    assert any('dependency cycle' in reason for item in plan['groups'] for reason in item['blockers'])
