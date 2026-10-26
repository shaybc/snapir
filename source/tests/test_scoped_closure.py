"""Check qualified closure semantics against fresh Mapper output, without running conversion."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_scoped_vault_identity import scoped_mapper, invoke_mapper
from models.java_classpath_index import JavaClasspathIndex
from tools.composer_mapper_tools.vault_importer import import_vault
from tools.conversion_tools.closure_builder_tool import build_scoped_operation_closure, build_operation_closure
from tools.state_store_tools.db import get_connection, create_all_tables


def workspace(root, wrapper='CCIColl'):
    from tools.conversion_tools.scoped_closure.collection_policy import INDEXED_WRAPPERS
    mappings = {'CCXML': 'example.Collection', 'CCString': 'example.Field',
                'FirstDecorator': 'example.FirstDecorator', 'SecondDecorator': 'example.SecondDecorator'}
    mappings.update({name: 'example.Collection' for name in INDEXED_WRAPPERS})
    for channel in ('XML', 'SME'):
        folder = root / 'Channel' / channel
        folder.mkdir(parents=True)
        registration = '<operDef id="Flows.xml" value="Flow"/>' if channel == 'XML' else '<operDef id="Caller.xml" value="Caller"/>'
        tags = ''.join(f'<field id="{name}" value="{fqcn}"/>' for name, fqcn in mappings.items())
        (folder / 'dse.ini').write_text('<dse.ini><kColl id="settings"><kColl id="files"><kColl id="selfDefOper">'
            + registration + '</kColl></kColl><kColl id="tags"><kColl id="formats">' + tags + '</kColl></kColl></kColl></dse.ini>')
    (root / 'Channel/SME/Caller.xml').write_text('''<XML><CCDSEServerOperation id="Caller" operationContext="Ctx">
      <opStep id="Call" implClass="com.ibm.il.dse.cc.cut.CCComplexOpStep" opExecuteName="Flow" on0Do="end"/>
    </CCDSEServerOperation><context id="Ctx" parent="Parent"><field id="Local" value="SME"/></context></XML>''')
    (root / 'Channel/XML/Flows.xml').write_text(f'''<XML>
      <CCDSEServerOperation id="Flow" operationContext="Ctx">
        <opStep id="Repeat" implClass="example.Work" fieldValue="first" on0Do="next" on0Return="One"/>
        <opStep id="Excluded" onlyFor="xml" implClass="example.Work" on0Do="next"/>
        <opStep id="Repeat" implClass="example.Work" fieldValue="second" on0Do="Repeat" on0Return="Two"/>
        <opStep id="Back" implClass="example.Work" on0Do="Repeat"/>
        <opStep id="Done" implClass="example.Work" onOtherDo="end"/>
        <refFormat name="csRequestFormat" refid="Req"/>
        <refFormat name="csReplyFormat" refid="One"/>
        <refFormat name="csErrorReplyFormat" refid="Err"/>
      </CCDSEServerOperation>
      <fmtDef id="Req"><{wrapper}>
        <CCString dataName="Same" value="first"/><FirstDecorator/>
        <CCString dataName="Same" value="second"/><SecondDecorator/>
        <refFmt refid="Leaf"/><refFmt refid="Leaf"/>
      </{wrapper}></fmtDef>
      <fmtDef id="One"><CCString dataName="Overwritten"/></fmtDef>
      <fmtDef id="One"><CCString dataName="Last"/></fmtDef>
      <fmtDef id="Two"><CCString dataName="Other"/></fmtDef>
      <fmtDef id="Err"><CCString dataName="Error"/></fmtDef>
      <fmtDef id="Leaf"><CCString dataName="LeafField"/></fmtDef>
      <context id="Ctx" parent="Parent"><field id="Local" value="XML"/></context>
      <context id="Parent" parent="nil"><field id="Inherited"/></context>
    </XML>''', encoding='utf-8')
    java = root / 'src/example'
    java.mkdir(parents=True)
    for name in ('Work', 'Field', 'Collection', 'FirstDecorator', 'SecondDecorator'):
        (java / (name + '.java')).write_text('package example;\npublic class ' + name + ' {}\n', encoding='utf-8')


def import_workspace(tmp_path, mapper, *, wrapper='CCIColl', change=None):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    workspace(root, wrapper)
    if change:
        change(root)
    result = invoke_mapper(mapper, root, vault)
    assert result.returncode == 0, result.stderr
    conn = get_connection(':memory:')
    create_all_tables(conn)
    config = SimpleNamespace(run_id='scoped', run_mode=SimpleNamespace(value='full_inventory'),
        target_channels=[], include_operations=None, exclude_operations=None, source_root=str(root))
    import_vault(conn, str(vault), config, progress=lambda message: None)
    return conn, root, vault


def build(conn, root, operation='Flow', channel='SME', **kwargs):
    return build_scoped_operation_closure(conn, operation, channel, 'scoped', str(root), **kwargs)


def profiled(conn, root, **kwargs):
    from models.external_dependency import ExternalDependencyRule
    kwargs.setdefault('profile', SimpleNamespace(external_dependencies=[ExternalDependencyRule(
        class_name='com.ibm.il.dse.cc.cut.CCComplexOpStep', treatment='replace')],
        composer_behavior_document=None))
    return build(conn, root, java_project='.', classpath_index=JavaClasspathIndex(), **kwargs)


def nodes(root):
    yield root
    for child in root.children:
        yield from nodes(child)


def test_routing_switches_and_context_override_are_qualified(tmp_path, scoped_mapper):
    conn, root, vault = import_workspace(tmp_path, scoped_mapper)
    closure = profiled(conn, root)
    assert closure.status == 'evidence_ready', closure.blocking_issues
    assert not closure.conversion_enabled
    with pytest.raises(ValueError, match='frozen'):
        closure.conversion_enabled = True
    assert [step.source_index for step in closure.steps] == [0, 2, 3, 4]
    assert [step.effective_index for step in closure.steps] == [0, 1, 2, 3]
    first, second, back, done = [step.source.note for step in closure.steps]
    assert closure.routing_graph[first]['on0Do'] == second
    assert closure.routing_graph[second]['on0Do'] == second
    assert closure.routing_graph[back]['on0Do'] == first
    assert closure.routing_graph[done]['onOtherDo'] is None
    assert closure.return_body_switches[first]['on0Return'] != closure.return_body_switches[second]['on0Return']
    request = closure.formats[closure.format_roles['csRequestFormat']]
    fields = [node for node in nodes(request) if node.attributes.get('dataName') == 'Same']
    assert len(fields) == 2 and fields[0].occurrence_id != fields[1].occurrence_id
    assert [field.decorators[0]['tag'] for field in fields] == ['FirstDecorator', 'SecondDecorator']
    reply = closure.formats[closure.format_roles['csReplyFormat']]
    assert 'Last' in str(reply.model_dump()) and 'Overwritten' not in str(reply.model_dump())
    assert closure.context_chain[0]['declared_fields'][0]['attributes']['value'] == 'SME'
    assert [level['entity_id'] for level in closure.context_chain] == ['Ctx', 'Parent']
    assert any(field['name'] == 'Inherited' and field['inherited'] for field in closure.context_fields)
    with pytest.raises(ValueError, match='conversion is gated'):
        build_operation_closure(conn, 'Flow', 'SME', 'scoped', str(root), str(vault))
    assert conn.execute('SELECT count(*) FROM operation_closures').fetchone()[0] == 0


def test_keyed_children_drop_overwritten_decorators_but_keep_references(tmp_path, scoped_mapper):
    conn, root, _ = import_workspace(tmp_path, scoped_mapper, wrapper='CCXML')
    closure = profiled(conn, root)
    assert closure.status == 'evidence_ready', closure.blocking_issues
    request = closure.formats[closure.format_roles['csRequestFormat']]
    fields = [node for node in nodes(request) if node.attributes.get('dataName') == 'Same']
    assert len(fields) == 1 and fields[0].attributes['value'] == 'second'
    assert [decorator['tag'] for decorator in fields[0].decorators] == ['SecondDecorator']
    references = [node for node in nodes(request) if node.tag == 'refFmt']
    assert len(references) == 2 and references[0].occurrence_id != references[1].occurrence_id
    assert references[0].reference_definition_id == references[1].reference_definition_id


def test_java_requires_profile_even_for_unique_candidate(tmp_path, scoped_mapper):
    conn, root, _ = import_workspace(tmp_path, scoped_mapper)
    closure = build(conn, root)
    assert closure.status == 'blocked'
    assert any('classpath profile' in issue.detail for issue in closure.blocking_issues)
    proven = profiled(conn, root)
    assert proven.status == 'evidence_ready', proven.blocking_issues
    assert {item['status'] for item in proven.java_origins} == {'verified_source'}


def test_source_revision_change_blocks_only_affected_contexts_and_callers(tmp_path, scoped_mapper):
    conn, root, _ = import_workspace(tmp_path, scoped_mapper)
    (root / 'src/example/Work.java').write_text('package example; public class Work { int changed; }')
    closure = profiled(conn, root, operation='Caller')
    assert closure.status == 'blocked'
    rows = [json.loads(row[0]) for row in conn.execute('SELECT closure_json FROM scoped_operation_closures')]
    assert {row['operation_id'] for row in rows} == {'Caller', 'Flow'}
    assert all(row['status'] == 'blocked' for row in rows)
    assert any('Called execution context' in issue.detail for issue in closure.blocking_issues)


def test_context_parent_cycle_blocks_and_persists_qualified_hierarchy(tmp_path, scoped_mapper):
    def change(root):
        path = root / 'Channel/XML/Flows.xml'
        path.write_text(path.read_text().replace('id="Parent" parent="nil"', 'id="Parent" parent="Ctx"'))
    conn, root, _ = import_workspace(tmp_path, scoped_mapper, change=change)
    closure = profiled(conn, root)
    assert closure.status == 'blocked'
    assert any('parent cycle' in issue.detail for issue in closure.blocking_issues)
    assert conn.execute('SELECT count(*) FROM scoped_context_hierarchies').fetchone()[0] == 1


def test_source_and_binary_collision_never_selects_arbitrary_origin(tmp_path, scoped_mapper):
    conn, root, _ = import_workspace(tmp_path, scoped_mapper)
    binary = JavaClasspathIndex(classes={'example.Work': ['jar:competing.jar']})
    closure = build(conn, root, java_project='.', classpath_index=binary)
    assert closure.status == 'blocked'
    assert any('Competing source/binary' in issue.detail for issue in closure.blocking_issues)


@pytest.mark.parametrize('encoding', ['utf-8', 'cp1255', 'ascii'])
def test_java_decoding_preserves_bytes_and_size_guard(tmp_path, monkeypatch, encoding):
    from tools.java_analysis_tools.java_source_reader import read_java_source
    from tools.source_discovery_tools import discover_java_sources
    from tools.source_discovery_tools.dependencies import classify_java_imports
    source = tmp_path / 'src/example/Work.java'
    source.parent.mkdir(parents=True)
    text = 'package example; public class Work { String text = "' + ('hello' if encoding == 'ascii' else 'שלום') + '"; }'
    source.write_bytes(text.encode(encoding))
    before = source.read_bytes()
    assert read_java_source(str(source)) == text
    index = discover_java_sources(str(tmp_path))
    assert index.classes['example.Work'] == [str(source.resolve())]
    assert classify_java_imports(str(source), index, JavaClasspathIndex()) == []
    monkeypatch.setattr('tools.java_analysis_tools.java_source_reader.MAX_SOURCE_CHARS_PER_CONVERSION', 5)
    with pytest.raises(ValueError, match='MAX_SOURCE_CHARS'):
        read_java_source(str(source))
    assert source.read_bytes() == before


def test_all_confirmed_wrappers_match_mapper_collection_policy():
    from tools.conversion_tools.scoped_closure.collection_policy import INDEXED_WRAPPERS, effective_children
    from xml.etree.ElementTree import fromstring
    source = Path(__file__).resolve().parents[1] / 'composer-mapper/src/main/java/il/co/dcd/composermapper/util/FormatCollectionPolicy.java'
    policy = source.read_text()
    for name in INDEXED_WRAPPERS:
        assert '"' + name + '"' in policy
        wrapper = fromstring(f'<{name}><CCString dataName="Same"/><CCString dataName="Same"/></{name}>')
        assert len(effective_children(wrapper, lambda child: False)) == 2
    assert len(INDEXED_WRAPPERS) == 12


def test_nested_same_name_definitions_keep_parent_occurrences(tmp_path, scoped_mapper):
    def change(root):
        path = root / 'Channel/XML/Flows.xml'
        path.write_text(path.read_text().replace('<refFmt refid="Leaf"/><refFmt refid="Leaf"/>',
            '<fmtDef id="Nested"><CCString dataName="NestedFirst"/></fmtDef>'
            '<fmtDef id="Nested"><CCString dataName="NestedSecond"/></fmtDef>'))
    conn, root, _ = import_workspace(tmp_path, scoped_mapper, change=change)
    closure = profiled(conn, root)
    assert closure.status == 'evidence_ready', closure.blocking_issues
    request = closure.formats[closure.format_roles['csRequestFormat']]
    nested = [node for node in nodes(request) if node.tag == 'fmtDef' and node.attributes['id'] == 'Nested']
    assert len(nested) == 2 and nested[0].definition_id != nested[1].definition_id
    assert all(node.collection_kind == 'definition' for node in nested)
    assert [node.children[0].attributes['dataName'] for node in nested] == ['NestedFirst', 'NestedSecond']


def test_context_storage_does_not_mix_channel_overrides(tmp_path, scoped_mapper):
    conn, root, _ = import_workspace(tmp_path, scoped_mapper)
    sme = profiled(conn, root)
    xml = profiled(conn, root, channel='XML')
    assert sme.status == xml.status == 'evidence_ready'
    assert sme.context_chain[0]['definition_id'] != xml.context_chain[0]['definition_id']
    assert conn.execute('SELECT count(*) FROM scoped_context_hierarchies').fetchone()[0] == 2
    assert len(xml.steps) == 5 and len(sme.steps) == 4


def test_context_route_mismatch_blocks_instead_of_rebuilding_silently(tmp_path, scoped_mapper):
    conn, root, _ = import_workspace(tmp_path, scoped_mapper)
    row = conn.execute("SELECT operation_identity,record_json FROM scoped_operation_contexts WHERE channel='SME' AND operation_id='Flow'").fetchone()
    record = json.loads(row[1])
    record['transition_targets'][record['step_notes'][0]]['on0Do'] = record['step_notes'][-1]
    conn.execute('UPDATE scoped_operation_contexts SET record_json=? WHERE operation_identity=?', (json.dumps(record), row[0]))
    closure = profiled(conn, root)
    assert closure.status == 'blocked'
    assert any('transition disagrees' in issue.detail for issue in closure.blocking_issues)


def test_same_package_java_dependency_uses_captured_coordinates(tmp_path, scoped_mapper):
    def change(root):
        java = root / 'src/example'
        (java / 'Helper.java').write_text('package example;\npublic class Helper {}\n')
        (java / 'Work.java').write_text('package example;\npublic class Work { Helper helper; }\n')
    conn, root, _ = import_workspace(tmp_path, scoped_mapper, change=change)
    closure = profiled(conn, root)
    assert closure.status == 'evidence_ready', closure.blocking_issues
    assert any(origin['fqcn'] == 'example.Helper' and origin['status'] == 'verified_source'
               for origin in closure.java_origins)


def test_uncaptured_new_java_helper_blocks_selected_source(tmp_path, scoped_mapper):
    def change(root):
        (root / 'src/example/Work.java').write_text('package example;\npublic class Work { Helper helper; }\n')
    conn, root, _ = import_workspace(tmp_path, scoped_mapper, change=change)
    (root / 'src/example/Helper.java').write_text('package example;\npublic class Helper {}\n')
    closure = profiled(conn, root)
    assert closure.status == 'blocked'
    assert any('not captured by intake' in issue.detail for issue in closure.blocking_issues)


def test_unrelated_broken_inventory_does_not_block_closure(tmp_path, scoped_mapper):
    def change(root):
        (root / 'src/example/Unused.java').write_text('package example;\npublic class Unused { UnknownType missing; }\n')
        path = root / 'Channel/XML/Flows.xml'
        path.write_text(path.read_text().replace('</XML>', '<fmtDef id="UnusedFormat"><NotMapped/></fmtDef></XML>'))
    conn, root, _ = import_workspace(tmp_path, scoped_mapper, change=change)
    closure = profiled(conn, root)
    assert closure.status == 'evidence_ready', closure.blocking_issues
    assert not any(origin['fqcn'] == 'example.Unused' for origin in closure.java_origins)
    assert 'UnusedFormat' not in str(closure.formats)


def test_known_return_code_requires_occurrence_route(tmp_path, scoped_mapper):
    def change(root):
        (root / 'src/example/Work.java').write_text('package example;\npublic class Work {\n public int execute() { return 7; }\n}\n')
    conn, root, _ = import_workspace(tmp_path, scoped_mapper, change=change)
    closure = profiled(conn, root)
    assert closure.status == 'blocked'
    assert any('Known return code' in issue.detail for issue in closure.blocking_issues)


def test_hash_names_remain_literal_during_qualified_closure(tmp_path, scoped_mapper):
    def change(root):
        for relative in ('Channel/XML/Flows.xml', 'Channel/SME/Caller.xml', 'Channel/XML/dse.ini'):
            path = root / relative
            path.write_text(path.read_text().replace('"Flow"', '"#Flow"').replace('"Req"', '"#Req%23"'))
    conn, root, _ = import_workspace(tmp_path, scoped_mapper, change=change)
    closure = profiled(conn, root, operation='#Flow')
    assert closure.status == 'evidence_ready', closure.blocking_issues
    assert '#Flow' in closure.entry_step_note
    assert closure.formats[closure.format_roles['csRequestFormat']].attributes['id'] == '#Req%23'


def test_cp1255_java_passes_complete_syntax_gate_without_byte_changes(tmp_path, scoped_mapper):
    def change(root):
        path = root / 'src/example/Work.java'
        path.write_bytes('package example;\npublic class Work {\n // שלום\n}\n'.encode('cp1255'))
    conn, root, _ = import_workspace(tmp_path, scoped_mapper, change=change)
    path = root / 'src/example/Work.java'
    before = path.read_bytes()
    closure = profiled(conn, root)
    assert closure.status == 'evidence_ready', closure.blocking_issues
    assert path.read_bytes() == before


def test_operation_call_cycle_is_not_a_step_or_context_cycle(tmp_path, scoped_mapper):
    def change(root):
        path = root / 'Channel/XML/Flows.xml'
        text = path.read_text().replace('<opStep id="Done" implClass="example.Work" onOtherDo="end"/>',
            '<opStep id="Done" implClass="com.ibm.il.dse.cc.cut.CCComplexOpStep" opExecuteName="Caller" onOtherDo="end"/>')
        path.write_text(text)
    conn, root, _ = import_workspace(tmp_path, scoped_mapper, change=change)
    closure = profiled(conn, root, operation='Caller')
    assert closure.status == 'evidence_ready', closure.blocking_issues
    assert not closure.conversion_enabled
    assert conn.execute('SELECT count(*) FROM scoped_operation_closures').fetchone()[0] == 2


def test_unresolved_exact_case_transition_blocks_without_redirect(tmp_path, scoped_mapper):
    def change(root):
        path = root / 'Channel/XML/Flows.xml'
        path.write_text(path.read_text().replace('id="Back" implClass="example.Work" on0Do="Repeat"',
                                               'id="Back" implClass="example.Work" on0Do="repeat"'))
    conn, root, _ = import_workspace(tmp_path, scoped_mapper, change=change)
    closure = profiled(conn, root)
    assert closure.status == 'blocked'
    assert any('Unresolved exact-case transition' in issue.detail for issue in closure.blocking_issues)


def test_guarded_java_read_rejects_changed_revision(tmp_path):
    from tools.java_analysis_tools.java_source_reader import read_java_source
    path = tmp_path / 'Source.java'
    path.write_text('class Source {}')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert read_java_source(str(path), expected_hash=digest) == 'class Source {}'
    path.write_text('class Source { int changed; }')
    with pytest.raises(ValueError, match='revision differs'):
        read_java_source(str(path), expected_hash=digest)


@pytest.mark.parametrize('contains_class', [True, False])
def test_retained_binary_origin_is_verified_not_just_trusted(tmp_path, scoped_mapper, contains_class):
    from zipfile import ZipFile
    from models.external_dependency import ExternalDependencyRule
    conn, root, _ = import_workspace(tmp_path, scoped_mapper)
    library = tmp_path / 'retained.jar'
    with ZipFile(library, 'w') as archive:
        archive.writestr('example/Work.class' if contains_class else 'example/Other.class', b'compiled evidence')
    profile = SimpleNamespace(external_dependencies=[ExternalDependencyRule(class_name='example.Work',
        treatment='retain', maven_coordinates='example:work:1')], composer_behavior_document=None)
    closure = build(conn, root, java_project='.', profile=profile,
                    classpath_index=JavaClasspathIndex(classes={'example.Work': ['jar:' + str(library)]}))
    if contains_class:
        assert closure.status == 'evidence_ready', closure.blocking_issues
        assert any(origin['status'] == 'verified_retention' for origin in closure.java_origins)
    else:
        assert closure.status == 'blocked'
        assert any('does not contain' in issue.detail for issue in closure.blocking_issues)


def test_empty_operation_format_reference_is_an_explicit_blocker():
    from xml.etree.ElementTree import fromstring
    from tools.conversion_tools.scoped_closure.formats import FormatResolver
    problems = []
    resolver = FormatResolver(None, SimpleNamespace(operation_id='Flow'), None, {},
                              lambda entity, detail, *kind: problems.append(detail))
    resolver.resolve(fromstring('<CCDSEServerOperation><refFormat name="csRequestFormat"/></CCDSEServerOperation>'), {})
    assert problems == ['Operation format reference requires name and refid']
