"""Exercise scoped Mapper generation against real duplicate source definitions."""

import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from tools.composer_mapper_tools.vault_manifest import read_vault_manifest
from tools.operation_call_tools.discovery import discover_operation_calls
from tools.operation_call_tools.ordering import operation_waves


@pytest.fixture(scope='module')
def scoped_mapper(tmp_path_factory):
    classes = tmp_path_factory.mktemp('scoped-mapper-classes')
    sources = Path(__file__).resolve().parents[1] / 'composer-mapper/src/main/java'
    result = subprocess.run(['javac', '--release', '25', '-encoding', 'UTF-8', '-d', str(classes),
                             *map(str, sources.rglob('*.java'))], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return classes


def make_workspace(root):
    for channel in ('INTERNET', 'IVR'):
        folder = root / 'Channel' / channel
        folder.mkdir(parents=True)
        (folder / 'dse.ini').write_text('<dse.ini><kColl id="settings"/></dse.ini>')
        (folder / 'operations.xml').write_text('''<XML>
          <CCDSEServerOperation id="A" operationContext="Ctx">
            <refFormat name="csRequestFormat" refid="Fmt"/>
            <fmtDef id="Fmt"><CCXML dataName="AField"/></fmtDef>
            <opStep id="Call" implClass="com.ibm.il.dse.cc.cut.CCComplexOpStep" opExecuteName="B" on0Do="Done"/>
            <opStep id="Done" implClass="org.example.Work"/>
          </CCDSEServerOperation>
          <CCDSEServerOperation id="B" operationContext="Ctx">
            <refFormat name="csRequestFormat" refid="Fmt"/>
            <fmtDef id="Fmt"><CCXML dataName="BField"/></fmtDef>
            <opStep id="Call" implClass="org.example.Work"/>
          </CCDSEServerOperation>
          <context id="Ctx" type="local"/>
          <fmtDef id="Unused"><CCXML dataName="UnusedField"/></fmtDef>
        </XML>''')
    for folder in ('project-one', 'project-two'):
        source = root / folder / 'org/example'
        source.mkdir(parents=True)
        (source / 'Work.java').write_text('package org.example;\npublic class Work {}\n')


def invoke_mapper(classes, root, vault, markdown=True):
    return subprocess.run(['java', '-cp', str(classes), 'il.co.dcd.composermapper.Main', '--root', str(root),
        '--vault', str(vault), '--vault-layout', 'scoped', '--workspace-id', 'fixture',
        '--md', str(markdown).lower()], capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize('markdown', [True, False])
def test_duplicate_operation_step_resource_names_survive(tmp_path, scoped_mapper, markdown):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    make_workspace(root)
    result = invoke_mapper(scoped_mapper, root, vault, markdown)
    assert result.returncode == 0, result.stderr
    manifest = read_vault_manifest(vault)
    operations = [e for e in manifest['entities'] if e['kind'] == 'operation' and e['operation_id']]
    assert {(e['channel'], e['entity_id']) for e in operations} == {
        ('INTERNET', 'A'), ('INTERNET', 'B'), ('IVR', 'A'), ('IVR', 'B')}
    assert {e['note'] for e in operations} == {
        f'channels/{channel}/operations/{operation}/operation.md'
        for channel in ('INTERNET', 'IVR') for operation in ('A', 'B')}
    formats = [e for e in manifest['entities'] if e['kind'] == 'format' and e['entity_id'] == 'Fmt']
    assert len({e['definition_id'] for e in formats}) == 4
    for entry in formats:
        assert entry['operation_id'] + 'Field' in (vault / entry['note']).read_text()
    for operation in operations:
        evidence = next(item for item in operation['java_resolution'] if item['fqcn'] == 'org.example.Work')
        assert evidence['status'] == 'unresolved_classpath'
        assert len(evidence['candidates']) == 2
        step = vault / operation['references']['opsteps:Call']
        assert step.name == 'Call.md'
        assert '  - ' + operation['entity_id'] in step.read_text()
    assert any(e['entity_id'] == 'Unused' for e in manifest['entities'])
    for entry in manifest['entities']:
        if not entry.get('operation_id'):
            if entry['kind'] == 'java_class':
                assert entry['note'] == 'unassigned/resources/classes/' + str(Path(entry['source_relative_path']).with_suffix('.md')).replace('\\', '/')
            else:
                assert Path(entry['note']).name == entry['entity_id'] + '.md'
                assert entry['note'].startswith('channels/' + entry['channel'] + '/resources/')
                assert '/operations/' in entry['note'] or '/duplicate/' in entry['note']
                assert entry['source_relative_path'] not in entry['note']
                assert 'XML[1]' not in entry['note']
    graph = discover_operation_calls(vault)
    assert graph['issues'] == []
    assert {(c['caller'], c['callee']) for c in graph['calls']} == {('INTERNET/A', 'INTERNET/B'), ('IVR/A', 'IVR/B')}
    assert operation_waves(graph)['INTERNET/A']['wave'] == 2
    assert operation_waves(graph)['IVR/B']['wave'] == 1
    assert invoke_mapper(scoped_mapper, root, vault).returncode != 0


def test_manifest_rejects_modified_notes_and_incomplete_output(tmp_path, scoped_mapper):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    make_workspace(root)
    assert invoke_mapper(scoped_mapper, root, vault).returncode == 0
    manifest = read_vault_manifest(vault)
    note = vault / manifest['entities'][0]['note']
    note.write_text(note.read_text() + '\nchanged\n')
    with pytest.raises(ValueError, match='differs'):
        read_vault_manifest(vault)
    (vault / 'vault-generation.json').write_text('{}')
    with pytest.raises(ValueError, match='Incomplete'):
        read_vault_manifest(vault)


def test_ambiguous_operation_is_diagnosed_without_overwrite(tmp_path, scoped_mapper):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    make_workspace(root)
    (root / 'Channel/INTERNET/duplicate.xml').write_text('<XML><CCDSEServerOperation id="A"/></XML>')
    assert invoke_mapper(scoped_mapper, root, vault).returncode == 0
    manifest = read_vault_manifest(vault)
    assert any('Ambiguous operation A' in d['detail'] for d in manifest['diagnostics'])
    occurrences = [e for e in manifest['entities'] if e['kind'] == 'operation' and e['entity_id'] == 'A'
                   and e['definition_channel'] == 'INTERNET']
    assert len(occurrences) == 2


def test_scoped_import_keeps_definition_and_usage_identity(tmp_path, scoped_mapper):
    from tools.composer_mapper_tools.vault_importer import import_vault
    from tools.composer_mapper_tools.scoped_vault_importer import require_qualified_conversion
    from tools.state_store_tools.db import get_connection, create_all_tables
    from tools.state_store_tools.operation_calls import get_contract
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    make_workspace(root)
    assert invoke_mapper(scoped_mapper, root, vault).returncode == 0
    conn = get_connection(':memory:')
    create_all_tables(conn)
    config = SimpleNamespace(run_id='scoped', run_mode=SimpleNamespace(value='full_inventory'),
                             target_channels=[], include_operations=None, exclude_operations=None)
    summary = import_vault(conn, str(vault), config)
    assert summary.operations == 4
    assert conn.execute("SELECT count(*) FROM scoped_source_definitions WHERE kind='opStep' AND logical_id='Call'").fetchone()[0] == 4
    assert conn.execute('SELECT count(*) FROM source_artifacts').fetchone()[0] == 0
    context = conn.execute("SELECT definition_id,count(*) FROM scoped_entity_usages WHERE record_json LIKE '%\"kind\": \"context\"%' GROUP BY definition_id").fetchall()
    assert sorted(row[1] for row in context) == [2, 2]
    assert 'AField' in get_contract(conn, 'scoped', 'INTERNET/A')['formats']['csRequestFormat']['markdown']
    assert 'BField' in get_contract(conn, 'scoped', 'INTERNET/B')['formats']['csRequestFormat']['markdown']
    with pytest.raises(ValueError, match='conversion is gated'):
        require_qualified_conversion(conn, 'scoped')
    import_vault(conn, str(vault), config)
    changed = json.loads((vault / 'vault-manifest.json').read_text())
    changed['producer'] = 'changed-evidence'
    (vault / 'vault-manifest.json').write_text(json.dumps(changed))
    with pytest.raises(ValueError, match='fresh run'):
        import_vault(conn, str(vault), config)


def test_copied_excel_generator_reads_scoped_vault(tmp_path, scoped_mapper):
    import shutil
    import sys
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    make_workspace(root)
    for channel in ('INTERNET', 'IVR'):
        folder = root / 'Channel' / channel
        operations = folder / 'selfDefOper'
        operations.mkdir()
        (folder / 'operations.xml').rename(operations / 'Operations.xml')
        defaults = folder / 'defaultFile'
        defaults.mkdir()
        (defaults / 'dsecontext.xml').write_text('<XML><context id="Ctx" type="local"/></XML>')
    assert invoke_mapper(scoped_mapper, root, vault).returncode == 0
    manifest = read_vault_manifest(vault)
    context_paths = {entry['note'] for entry in manifest['entities'] if entry['kind'] == 'context'}
    assert 'channels/INTERNET/resources/contexts/defaultFile/Ctx.md' in context_paths
    assert 'channels/INTERNET/resources/contexts/selfDefOper/Operations/Ctx.md' in context_paths
    python = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    python = str(python) if python.is_file() else sys.executable
    if subprocess.run([python, '-c', 'import openpyxl'], capture_output=True).returncode:
        pytest.skip('Standalone workbook verification requires openpyxl')
    script = tmp_path / 'Excel Generator.py'
    shutil.copy2(Path(__file__).resolve().parents[2] / 'Excel Generator.py', script)
    result = subprocess.run([python, str(script), str(vault), '--include-relationships'],
                             cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    output = tmp_path / 'operation-migration.xlsx'
    result = subprocess.run([python, '-c',
        "from openpyxl import load_workbook; import sys; w=load_workbook(sys.argv[1]); "
        "assert w.sheetnames==['Migration Plan','Operations','Relationships']; "
        "assert w['Operations'].max_row==9; assert w['Relationships'].max_row==7; "
        "assert sorted(r[4] for r in list(w['Operations'].values)[5:])==[1,1,2,2]", str(output)],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_standalone_discovery_matches_current_shared_implementation():
    import ast
    root = Path(__file__).resolve().parents[2]
    standalone = ast.parse((root / 'Excel Generator.py').read_text(encoding='utf-8-sig'))
    bundled = {node.name: ast.dump(node, include_attributes=False)
               for node in standalone.body if isinstance(node, ast.FunctionDef)}
    for relative in ('composer_mapper_tools/vault_manifest.py', 'operation_call_tools/discovery.py', 'operation_call_tools/ordering.py'):
        shared = ast.parse((root / 'source/tools' / relative).read_text(encoding='utf-8-sig'))
        for node in shared.body:
            if isinstance(node, ast.FunctionDef) and node.name != 'ordered_operations':
                assert bundled[node.name] == ast.dump(node, include_attributes=False), node.name


def test_parse_failure_never_publishes_complete_manifest(tmp_path, scoped_mapper):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    make_workspace(root)
    (root / 'Channel/INTERNET/broken.xml').write_text('<XML><broken>')
    result = invoke_mapper(scoped_mapper, root, vault)
    assert result.returncode != 0
    assert (vault / 'vault-generation.json').exists()
    assert not (vault / 'vault-manifest.json').exists()
    with pytest.raises(ValueError, match='Incomplete'):
        read_vault_manifest(vault)


def test_legacy_collision_is_reported_without_changing_legacy_generation(tmp_path, scoped_mapper):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    make_workspace(root)
    vault.mkdir()
    existing = vault / 'operations/keep.md'
    existing.parent.mkdir()
    existing.write_text('keep existing output')
    result = subprocess.run(['java', '-cp', str(scoped_mapper), 'il.co.dcd.composermapper.Main',
        '--root', str(root), '--vault', str(vault), '--clean', 'false'], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert 'Legacy vault identity collision' in result.stderr
    assert 'Legacy vault identity collision' in (vault / 'analysis/entity-collisions.md').read_text()
    assert existing.read_text() == 'keep existing output'


def test_xml_project_java_inventory_uses_declared_channel(tmp_path, scoped_mapper):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    source = root / 'project-without-channel-in-name/src'
    declaration = source / 'Xml Definition/Channel/XML'
    declaration.mkdir(parents=True)
    (declaration / 'dse.ini').write_text('<dse.ini/>')
    java = source / 'com/ibm/il/dse/cc/cut/CCDSEServerOperation.java'
    java.parent.mkdir(parents=True)
    java.write_text('package com.ibm.il.dse.cc.cut;\npublic class CCDSEServerOperation {}')
    assert invoke_mapper(scoped_mapper, root, vault).returncode == 0
    manifest = read_vault_manifest(vault)
    entry = next(e for e in manifest['entities'] if e['kind'] == 'java_class')
    assert entry['channel'] == entry['definition_channel'] == 'XML'
    assert entry['note'] == 'channels/XML/resources/classes/project-without-channel-in-name/src/com/ibm/il/dse/cc/cut/CCDSEServerOperation.md'
    assert entry['source_relative_path'] == 'project-without-channel-in-name/src/com/ibm/il/dse/cc/cut/CCDSEServerOperation.java'
    assert not (vault / 'unassigned').exists()


def test_context_inventory_keeps_only_resource_origins(tmp_path, scoped_mapper):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    channel = root / 'WSBCC_IVR/src/Xml Definition/Channel/IVR'
    defaults = channel / 'defaultFile'
    operations = channel / 'selfDefOper'
    defaults.mkdir(parents=True)
    operations.mkdir()
    (channel / 'dse.ini').write_text('<dse.ini/>')
    (defaults / 'dsecontext.xml').write_text('<XML><context id="Ctx" type="op"/></XML>')
    (operations / 'Example.xml').write_text('''<XML>
      <CCDSEServerOperation id="ExampleOp" operationContext="Ctx"/>
      <context id="Ctx" type="op"/>
    </XML>''')
    assert invoke_mapper(scoped_mapper, root, vault).returncode == 0
    manifest = read_vault_manifest(vault)
    contexts = [entry for entry in manifest['entities'] if entry['kind'] == 'context']
    assert {entry['note'] for entry in contexts} == {
        'channels/IVR/resources/contexts/defaultFile/Ctx.md',
        'channels/IVR/resources/contexts/selfDefOper/Example/Ctx.md'}
    assert len({entry['definition_id'] for entry in contexts}) == 2
    assert all(entry['source_relative_path'].startswith('WSBCC_IVR/src/') for entry in contexts)
    assert all(entry['source_selector'] == '/XML[1]/context[1]' for entry in contexts)
    assert any('Ambiguous context Ctx' in item['detail'] for item in manifest['diagnostics'])
