"""Exercise scoped Mapper generation against real duplicate source definitions."""

import hashlib
import json
import os
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


def test_scoped_progress_records_context_totals_and_elapsed(tmp_path, scoped_mapper):
    import re
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    make_workspace(root)
    result = invoke_mapper(scoped_mapper, root, vault)
    assert result.returncode == 0, result.stderr
    log = (vault / 'composer-mapper.log').read_text(encoding='utf-8')
    assert all(re.match(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})\]', line)
               for line in log.splitlines())
    assert 'Discovering source files:' in result.stdout
    assert 'Planned 2 channels and 4 operation views' in log
    assert 'Channel 1/2 INTERNET' in log and 'Channel 2/2 IVR' in log
    for channel in ('INTERNET', 'IVR'):
        for operation in ('A', 'B'):
            assert re.search('Starting operation [1-4]/4 ' + channel + '/' + operation, log)
    assert 'remaining=0' in log
    assert 'Writing unused source inventory:' in log
    assert 'Finalizing manifest and note metadata:' in log and 'Writing manifest:' in log
    assert 'operation views completed=4 | skipped=0' in log
    assert re.search(r'SUCCESS .*elapsed=\d+:\d{2}:\d{2}', log)
    assert 'SUCCESS' in result.stdout and 'elapsed=' in result.stdout
    assert (vault / 'vault-manifest.json').is_file()
    assert not (vault / 'vault-generation.json').exists()


@pytest.mark.parametrize('mode', ['values', 'large', 'failure'])
def test_manifest_json_streaming(tmp_path, scoped_mapper, mode):
    harness = tmp_path / 'JsonStreamingProbe.java'
    harness.write_text(r'''
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import il.co.dcd.composermapper.util.JsonOutput;
import il.co.dcd.composermapper.render.VaultManifestWriter;
public class JsonStreamingProbe {
    public static void main(String[] args) throws Exception {
        Path output = Path.of(args[1]);
        if (args[0].equals("failure")) {
            Object broken = new Object() {
                public String toString() { throw new IllegalStateException("injected write failure"); }
            };
            try {
                new VaultManifestWriter("fixture").finish(output,
                    List.of(Map.of("message", broken)), List.of("XML"));
                throw new AssertionError("Expected failure");
            } catch (IllegalStateException expected) {
                if (!expected.getMessage().equals("injected write failure")) throw expected;
            }
            if (Files.exists(output.resolve("vault-manifest.json"))) throw new AssertionError("Published failed manifest");
            if (!Files.exists(output.resolve("vault-manifest.json.tmp"))) throw new AssertionError("Expected temporary file");
            return;
        }
        Object value;
        if (args[0].equals("large")) {
            String payload = "x".repeat(4096);
            value = (Iterable<String>) () -> new Iterator<String>() {
                int remaining = 20000;
                public boolean hasNext() { return remaining > 0; }
                public String next() { remaining--; return payload; }
            };
        } else {
            Map<String, Object> sample = new LinkedHashMap<>();
            sample.put("text", "quote\" slash\\ newline\n return\r tab\t control\u0001 שלום 😀");
            sample.put("values", Arrays.asList(null, true, false, 42, 1.5, List.of(), Map.of()));
            value = sample;
        }
        try (var writer = Files.newBufferedWriter(output, StandardCharsets.UTF_8)) {
            JsonOutput.write(value, writer);
        }
        if (args[0].equals("values") && !Files.readString(output).equals(JsonOutput.encode(value)))
            throw new AssertionError("Changed encoding");
    }
}
''', encoding='utf-8')
    compiled = subprocess.run(['javac', '-encoding', 'UTF-8', '-cp', str(scoped_mapper), '-d', str(tmp_path), str(harness)],
                              capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stderr
    output = tmp_path if mode == 'failure' else tmp_path / 'output.json'
    result = subprocess.run(['java', '-Xmx24m', '-cp', os.pathsep.join([str(scoped_mapper), str(tmp_path)]),
                             'JsonStreamingProbe', mode, str(output)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    if mode == 'large':
        # Output exceeds the 24 MiB heap; lazy elements must not become serialized copies in memory.
        assert output.stat().st_size == 1 + 20000 * (4096 + 3)
    elif mode == 'values':
        assert json.loads(output.read_text(encoding='utf-8')) == {
            'text': 'quote" slash\\ newline\n return\r tab\t control\x01 שלום 😀',
            'values': [None, True, False, 42, 1.5, [], {}],
        }


def test_console_heartbeat_reports_long_running_work(tmp_path, scoped_mapper):
    harness = tmp_path / 'ProgressProbe.java'
    harness.write_text('''
import java.nio.file.Path;
import il.co.dcd.composermapper.service.MapperProgress;
public class ProgressProbe {
    public static void main(String[] args) throws Exception {
        try (var progress = new MapperProgress(Path.of(args[0]), System.nanoTime())) {
            progress.event("Starting operation 1/2 INTERNET/SlowOperation", false);
            Thread.sleep(5500);
        }
    }
}
''', encoding='utf-8')
    compiled = subprocess.run(['javac', '-cp', str(scoped_mapper), '-d', str(tmp_path), str(harness)],
                              capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stderr
    log = tmp_path / 'progress.log'
    result = subprocess.run(['java', '-cp', os.pathsep.join([str(scoped_mapper), str(tmp_path)]),
                             'ProgressProbe', str(log)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert 'Progress: Starting operation 1/2 INTERNET/SlowOperation | elapsed=' in result.stdout
    assert 'Starting operation 1/2 INTERNET/SlowOperation' in log.read_text(encoding='utf-8')


@pytest.mark.parametrize('encoding', ['utf-8', 'cp1255', 'ascii'])
def test_java_source_reader_preserves_text_and_source_bytes(tmp_path, scoped_mapper, encoding):
    text = 'package example;\npublic class Encoded {}\n// ' + ('plain' if encoding == 'ascii' else '\u05e9\u05dc\u05d5\u05dd')
    source = tmp_path / 'Encoded.java'
    original = text.encode(encoding)
    source.write_bytes(original)
    harness = tmp_path / 'CheckEncoding.java'
    harness.write_text('''
import java.nio.file.Path;
import il.co.dcd.composermapper.util.JavaSourceReader;
import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.index.JavaClassIndexer;
import il.co.dcd.composermapper.parser.JavaClassParser;
public class CheckEncoding {
    public static void main(String[] args) throws Exception {
        Path source = Path.of(args[0]);
        String text = JavaSourceReader.read(source);
        if (!text.endsWith(args[1])) throw new AssertionError("Source text changed");
        Indexes indexes = Indexes.create();
        new JavaClassIndexer().index(source, indexes);
        if (!indexes.classToSource().containsKey("example.Encoded")) throw new AssertionError("Index failed");
        if (!new JavaClassParser().parse(source).getFullyQualifiedName().equals("example.Encoded"))
            throw new AssertionError("Parse failed");
    }
}
''', encoding='utf-8')
    compiled = subprocess.run(['javac', '-cp', str(scoped_mapper), '-d', str(tmp_path), str(harness)],
                              capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stderr
    result = subprocess.run(['java', '-cp', os.pathsep.join([str(scoped_mapper), str(tmp_path)]),
                             'CheckEncoding', str(source), text.split('// ')[1]],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert ('using Windows-1255' in result.stderr) == (encoding == 'cp1255')
    assert source.read_bytes() == original


def test_scoped_mapper_accepts_mixed_java_encodings(tmp_path, scoped_mapper):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    make_workspace(root)
    originals = {}
    for name, encoding in [('Utf8', 'utf-8'), ('HebrewWindows', 'cp1255'), ('Plain', 'ascii')]:
        path = root / 'project-one' / (name + '.java')
        text = 'package example;\npublic class ' + name + ' {}\n// '
        text += 'plain' if encoding == 'ascii' else '\u05e9\u05dc\u05d5\u05dd'
        originals[path] = text.encode(encoding)
        path.write_bytes(originals[path])
    result = invoke_mapper(scoped_mapper, root, vault)
    assert result.returncode == 0, result.stderr
    assert 'using Windows-1255' in result.stderr
    manifest = read_vault_manifest(vault)
    java_entities = [entry for entry in manifest['entities'] if entry['kind'] == 'java_class']
    for path, original in originals.items():
        assert path.read_bytes() == original
        assert any(entry['source_relative_path'] == path.relative_to(root).as_posix()
                   for entry in java_entities)


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


@pytest.mark.parametrize('markdown', [True, False])
@pytest.mark.parametrize('restriction', ['', 'onlyFor="internet"'])
def test_repeated_steps_preserve_occurrences_and_positional_routing(tmp_path, scoped_mapper, markdown, restriction):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    folder = root / 'Channel/INTERNET'
    folder.mkdir(parents=True)
    (folder / 'dse.ini').write_text('<dse.ini/>')
    source = root / 'Channel/INTERNET/operations.xml'
    source.write_text('''<XML><CCDSEServerOperation id="A">
      <opStep id="Start" on0Do="Repeat"/>
      <opStep id="Repeat" implClass="com.ibm.il.dse.cc.cut.CCComplexOpStep" opExecuteName="B" on0Do="next"/>
      <opStep id="Middle" on0Do="Repeat" on1Do="Start" on2Do="repeat"/>
      <opStep id="Repeat" RESTRICTION implClass="com.ibm.il.dse.cc.cut.CCComplexOpStep"
              opExecuteName="C" on0Do="Repeat"/>
      <opStep id="Last" on0Do="Repeat" on1Do="next" on2Do="end"/>
    </CCDSEServerOperation><CCDSEServerOperation id="B"/><CCDSEServerOperation id="C"/></XML>'''.replace('RESTRICTION', restriction))
    original = source.read_bytes()
    result = invoke_mapper(scoped_mapper, root, vault, markdown)
    assert result.returncode == 0, result.stderr
    manifest = read_vault_manifest(vault)
    steps = sorted([e for e in manifest['entities'] if e['kind'] == 'opStep' and e['operation_id'] == 'A'],
                   key=lambda e: e['step_index'])
    assert [e['entity_id'] for e in steps] == ['Start', 'Repeat', 'Middle', 'Repeat', 'Last']
    assert len({e['definition_id'] for e in steps}) == 5
    assert len({e['note'] for e in steps}) == 5
    operation_entry = next(e for e in manifest['entities'] if e['kind'] == 'operation' and e['operation_id'] == 'A')
    assert operation_entry['step_notes'] == [e['note'] for e in steps]
    assert operation_entry['entry_step_note'] == steps[0]['note']
    assert 'opsteps:Repeat' not in operation_entry['references']
    assert steps[1]['note'].endswith('/opsteps/occurrences/2/Repeat.md')
    assert steps[3]['note'].endswith('/opsteps/occurrences/4/Repeat.md')
    assert steps[0]['transition_targets']['on0Do'] == steps[1]['note']
    assert steps[1]['transition_targets']['on0Do'] == steps[2]['note']
    assert steps[2]['transition_targets']['on0Do'] == steps[3]['note']
    assert steps[2]['transition_targets']['on1Do'] == steps[0]['note']
    assert 'on2Do' not in steps[2]['transition_targets']  # Named matching is case-sensitive.
    assert steps[3]['transition_targets']['on0Do'] == steps[3]['note']
    assert steps[4]['transition_targets'] == {'on0Do': steps[1]['note']}
    for entry in steps:
        note = (vault / entry['note']).read_text(encoding='utf-8')
        assert 'entity_id: ' + entry['entity_id'] in note
        assert 'step_index: ' + str(entry['step_index']) in note
        for target in entry['transition_targets'].values():
            assert (target if markdown else target[:-3] + '|') in note
    operation = (vault / 'channels/INTERNET/operations/A/operation.md').read_text(encoding='utf-8')
    assert all('step_occurrence_' + str(i) in operation for i in range(5))
    assert 'Unresolved: repeat' in operation
    graph = discover_operation_calls(vault)
    assert graph['issues'] == []
    assert [(c['step'], c['callee']) for c in graph['calls']] == [('Repeat', 'INTERNET/B'), ('Repeat', 'INTERNET/C')]
    assert [c['transitions'] for c in graph['calls']] == [{'on0Do': 'next'}, {'on0Do': 'Repeat'}]
    assert source.read_bytes() == original


@pytest.mark.parametrize('markdown', [True, False])
def test_only_for_variants_keep_channel_calls_and_source_occurrences(tmp_path, scoped_mapper, markdown):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    for channel in ('XML', 'BANKADMIN', 'INTERNET', 'IVR'):
        folder = root / 'Channel' / channel
        folder.mkdir(parents=True)
        imports = '' if channel == 'XML' else '<kColl id="import"><field id="XML"/></kColl>'
        (folder / 'dse.ini').write_text('<dse.ini>' + imports + '</dse.ini>')
    source = root / 'Channel/XML/operations.xml'
    source.write_text('''<XML>
      <CCDSEServerOperation id="A">
        <opStep id="Call" onlyFor="bankadmin" implClass="com.ibm.il.dse.cc.cut.CCComplexOpStep"
                opExecuteName="B" on0Do="Done"/>
        <opStep id="Call" onlyFor="internet" implClass="com.ibm.il.dse.cc.cut.CCComplexOpStep"
                opExecuteName="C" on0Do="Done"/>
        <opStep id="Done" onOtherDo="end"/>
        <opStep id="Shared" onlyFor=" BANKADMIN, internet " onOtherDo="end"/>
      </CCDSEServerOperation>
      <CCDSEServerOperation id="B"/>
      <CCDSEServerOperation id="C"/>
    </XML>''')
    original = source.read_bytes()
    result = invoke_mapper(scoped_mapper, root, vault, markdown)
    assert result.returncode == 0, result.stderr
    manifest = read_vault_manifest(vault)
    calls = [e for e in manifest['entities'] if e['kind'] == 'opStep' and e['entity_id'] == 'Call']
    assert {(e['channel'], e['operation_id']) for e in calls} == {('BANKADMIN', 'A'), ('INTERNET', 'A')}
    assert len({e['definition_id'] for e in calls}) == 2
    for channel, target in [('BANKADMIN', 'B'), ('INTERNET', 'C')]:
        note = vault / f'channels/{channel}/operations/A/opsteps/Call.md'
        text = note.read_text(encoding='utf-8')
        assert 'opExecuteName: `' + target + '`' in text
        assert 'unresolved `Done`' not in text
        assert ('Done.md' if markdown else '[[channels/') in text
        operation = (vault / f'channels/{channel}/operations/A/operation.md').read_text(encoding='utf-8')
        assert 'entry_step: Call' in operation
        assert operation.count('*(onlyFor:') == 2
    for channel in ('XML', 'IVR'):
        operation = (vault / f'channels/{channel}/operations/A/operation.md').read_text(encoding='utf-8')
        assert 'entry_step: Done' in operation
        assert 'onlyFor:' not in operation
        assert not (vault / f'channels/{channel}/operations/A/opsteps/Call.md').exists()
    graph = discover_operation_calls(vault)
    assert graph['issues'] == []
    assert {(c['caller'], c['callee']) for c in graph['calls']} == {
        ('BANKADMIN/A', 'BANKADMIN/B'), ('INTERNET/A', 'INTERNET/C')}
    assert source.read_bytes() == original

    # If no consuming channel is selected, both variants still survive in inventory.
    inventory_vault = tmp_path / 'inventory-vault'
    result = subprocess.run(['java', '-cp', str(scoped_mapper), 'il.co.dcd.composermapper.Main',
        '--root', str(root), '--vault', str(inventory_vault), '--vault-layout', 'scoped',
        '--workspace-id', 'fixture', '--channel', 'IVR'], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    inventory = read_vault_manifest(inventory_vault)
    variants = [e for e in inventory['entities'] if e['kind'] == 'opStep' and e['entity_id'] == 'Call']
    assert len(variants) == 2
    assert {e['definition_id'] for e in variants} == {e['definition_id'] for e in calls}
    assert all('/onlyFor/' in e['note'] for e in variants)
    assert len({e['note'] for e in variants}) == 2


@pytest.mark.parametrize('markdown', [True, False])
@pytest.mark.parametrize('inventory_only', [False, True])
def test_case_variant_steps_use_ordered_occurrence_folders(tmp_path, scoped_mapper, markdown, inventory_only):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    channel = root / 'Channel/XML'
    channel.mkdir(parents=True)
    (channel / 'dse.ini').write_text('<dse.ini/>')
    restriction = 'onlyFor="internet"' if inventory_only else ''
    source = channel / 'operation.xml'
    source.write_text('''<XML><CCDSEServerOperation id="CaseVariantsOp">
      <opStep id="Start" on0Do="SetSITE"/>
      <opStep id="SetSITE" RESTRICTION implClass="example.SetField" fieldName="SITE" fieldValue="Retail" on0Do="next"/>
      <opStep id="Middle" on0Do="SetSite" on1Do="SetSITE"/>
      <opStep id="SetSite" RESTRICTION implClass="example.SetField" fieldName="SITE" fieldValue="RETAIL" on0Do="end"/>
    </CCDSEServerOperation></XML>'''.replace('RESTRICTION', restriction))
    original = source.read_bytes()
    result = invoke_mapper(scoped_mapper, root, vault, markdown)
    assert result.returncode == 0, result.stderr
    manifest = read_vault_manifest(vault)
    entries = [entry for entry in manifest['entities'] if entry['kind'] == 'opStep'
               and entry['entity_id'] in {'SetSITE', 'SetSite'}]
    assert len(entries) == 2
    by_name = {entry['entity_id']: entry for entry in entries}
    assert len({entry['note'].lower() for entry in entries}) == 2
    assert len({entry['definition_id'] for entry in entries}) == 2
    for name, value in [('SetSITE', 'Retail'), ('SetSite', 'RETAIL')]:
        entry = by_name[name]
        note = (vault / entry['note']).read_text(encoding='utf-8')
        assert 'entity_id: ' + name in note
        assert 'fieldValue: `' + value + '`' in note
        assert 'qualified_entity_id: ' + entry['definition_id'] in note
        assert '/occurrences/' in entry['note']
        assert bool(entry['operation_id']) != inventory_only
    if not inventory_only:
        assert by_name['SetSITE']['note'].endswith('/occurrences/2/SetSITE.md')
        assert by_name['SetSite']['note'].endswith('/occurrences/4/SetSite.md')
        active = {entry['entity_id']: entry for entry in manifest['entities']
                  if entry['kind'] == 'opStep' and entry['operation_id'] == 'CaseVariantsOp'}
        assert active['Start']['transition_targets']['on0Do'] == by_name['SetSITE']['note']
        assert active['Middle']['transition_targets']['on0Do'] == by_name['SetSite']['note']
        assert active['Middle']['transition_targets']['on1Do'] == by_name['SetSITE']['note']
        assert by_name['SetSITE']['transition_targets']['on0Do'] == active['Middle']['note']
    assert source.read_bytes() == original


def test_operation_paths_are_reserved_before_any_note_is_written(tmp_path, scoped_mapper):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    channel = root / 'Channel/XML'
    channel.mkdir(parents=True)
    (channel / 'dse.ini').write_text('<dse.ini/>')
    source = channel / 'operation.xml'
    source.write_text('''<XML><CCDSEServerOperation id="A">
      <refFormat name="csRequestFormat" refid="Request"/>
      <refFormat name="csReplyFormat" refid="request"/>
      <fmtDef id="Request"><CCXML dataName="Input"/></fmtDef>
      <fmtDef id="request"><CCXML dataName="Output"/></fmtDef>
    </CCDSEServerOperation></XML>''')
    result = invoke_mapper(scoped_mapper, root, vault)
    assert result.returncode != 0
    assert 'Duplicate note path before writing:' in result.stderr
    assert 'first:' in result.stderr and 'conflicting:' in result.stderr
    assert str(source.resolve()) in result.stderr
    assert '/fmtDef[1]' in result.stderr and '/fmtDef[2]' in result.stderr
    assert not (vault / 'channels/XML/operations/A/operation.md').exists()
    assert not list(vault.rglob('*.md'))
    assert (vault / 'vault-generation.json').exists()
    assert not (vault / 'vault-manifest.json').exists()


@pytest.mark.parametrize('selected', [False, True])
@pytest.mark.parametrize('identical', [False, True])
def test_duplicate_registry_formats_use_last_declaration(tmp_path, scoped_mapper, selected, identical):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    channel = root / 'Channel/XML'
    channel.mkdir(parents=True)
    (channel / 'dse.ini').write_text('<dse.ini/>')
    source = channel / 'formats.xml'
    operation = '<CCDSEServerOperation id="A"><refFormat name="csRequestFormat" refid="Repeated"/></CCDSEServerOperation>' if selected else ''
    first_value = 'LastValue' if identical else 'FirstValue'
    source.write_text(f'''<XML>{operation}
      <fmtDef id="Repeated"><CCXML dataName="{first_value}">
        <fmtDef id="Child"><CCString dataName="OldChild"/></fmtDef>
      </CCXML></fmtDef>
      <fmtDef id="Repeated"><CCXML dataName="LastValue">
        <fmtDef id="Child"><CCString dataName="{'OldChild' if identical else 'NewChild'}"/></fmtDef>
      </CCXML></fmtDef>
    </XML>''', encoding='utf-8')
    original = source.read_bytes()
    result = invoke_mapper(scoped_mapper, root, vault)
    assert result.returncode == 0, result.stderr
    formats = [entry for entry in read_vault_manifest(vault)['entities'] if entry['kind'] == 'format']
    assert len(formats) == 2
    parent = next(entry for entry in formats if entry['entity_id'] == 'Repeated')
    assert parent['source_selector'] == '/XML[1]/fmtDef[2]'
    assert 'LastValue' in (vault / parent['note']).read_text(encoding='utf-8')
    child = next(entry for entry in formats if entry['entity_id'] == 'Child')
    assert child['source_selector'].startswith('/XML[1]/fmtDef[2]/')
    assert source.read_bytes() == original


@pytest.mark.parametrize('markdown', [True, False])
@pytest.mark.parametrize('parent_selected', [False, True])
def test_nested_format_inventory_retains_parent_order_and_references(tmp_path, scoped_mapper, markdown, parent_selected):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    channel = root / 'Channel/XML'
    folder = channel / 'selfDefOper'
    folder.mkdir(parents=True)
    (channel / 'dse.ini').write_text('<dse.ini/>')
    operation = '<CCDSEServerOperation id="A"><refFormat name="hostSendFormat" refid="GAC4HostSeFmt"/></CCDSEServerOperation>' if parent_selected else ''
    source = folder / 'Alt_GAC4.xml'
    source.write_text('''<XML>OPERATION
      <fmtDef id="GAC4HostSeFmt"><CCIColl dataName="GAC4">
        <refFmt refid="AltMessageHeaderFmt"/>
        <fmtDef id="GAC4HostSeSwitchCaseFmt"><SwitchCaseFormat>
          <caseRefFmt keyName="RequestID" keyValue="1"><refFmt refid="RequestBranchFmt"/></caseRefFmt>
          <caseRefFmt keyName="RequestID" keyValue="2">
            <fmtDef id="InlinePayloadFmt"><CCString dataName="NestedPayload"/></fmtDef>
          </caseRefFmt>
        </SwitchCaseFormat></fmtDef>
        <fmtDef id="GAC4HostSeSwitchCaseFmt"><SwitchCaseFormat>
          <caseRefFmt keyName="AccountNumberFlag" keyValue="N"><refFmt refid="SessionDataFmt"/></caseRefFmt>
        </SwitchCaseFormat></fmtDef>
      </CCIColl></fmtDef>
      <fmtDef id="GAC4NextHostSeFmt"><PSIONewXMLFormat><refFmt refid="RequestBranchFmt"/></PSIONewXMLFormat></fmtDef>
      <fmtDef id="AltMessageHeaderFmt"><CCString dataName="Header"/></fmtDef>
      <fmtDef id="RequestBranchFmt"><CCString dataName="Request"/></fmtDef>
      <fmtDef id="SessionDataFmt"><CCString dataName="Session"/></fmtDef>
    </XML>'''.replace('OPERATION', operation), encoding='utf-8')
    original = source.read_bytes()
    result = invoke_mapper(scoped_mapper, root, vault, markdown)
    assert result.returncode == 0, result.stderr
    manifest = read_vault_manifest(vault)
    formats = [entry for entry in manifest['entities'] if entry['kind'] == 'format']
    assert len(formats) == 8
    assert len({entry['definition_id'] for entry in formats}) == 8
    assert len({entry['note'].lower() for entry in formats}) == 8
    parent = next(entry for entry in formats if entry['entity_id'] == 'GAC4HostSeFmt')
    base = 'channels/XML/resources/formats/selfDefOper/Alt_GAC4/'
    if not parent_selected:
        assert parent['note'] == base + 'GAC4HostSeFmt.md'
    assert next(entry for entry in formats if entry['entity_id'] == 'GAC4NextHostSeFmt')['note'] == base + 'GAC4NextHostSeFmt.md'
    nested = sorted([entry for entry in formats if entry['entity_id'] == 'GAC4HostSeSwitchCaseFmt'],
                    key=lambda entry: entry['nested_format_index'])
    selectors = ['/XML[1]/fmtDef[1]/CCIColl[1]/fmtDef[1]',
                 '/XML[1]/fmtDef[1]/CCIColl[1]/fmtDef[2]']
    for ordinal, (entry, selector) in enumerate(zip(nested, selectors), 1):
        assert entry['note'] == base + f'GAC4HostSeFmt/nested/{ordinal}/GAC4HostSeSwitchCaseFmt.md'
        assert entry['source_selector'] == selector
        assert entry['parent_definition_id'] == parent['definition_id']
        assert entry['parent_source_selector'] == parent['source_selector']
        # Canonical source identity is independent of the new Markdown location.
        digest = hashlib.sha256()
        for field in ('fixture', 'format', 'Channel/XML/selfDefOper/Alt_GAC4.xml', selector):
            encoded = field.encode('utf-8')
            digest.update(str(len(encoded)).encode() + b':' + encoded)
        assert entry['definition_id'] == digest.hexdigest()
    first = (vault / nested[0]['note']).read_text(encoding='utf-8')
    second = (vault / nested[1]['note']).read_text(encoding='utf-8')
    assert 'keyName="RequestID"' in first and 'refid="RequestBranchFmt"' in first
    assert 'keyName="AccountNumberFlag"' in second and 'refid="SessionDataFmt"' in second
    deep = next(entry for entry in formats if entry['entity_id'] == 'InlinePayloadFmt')
    assert deep['note'] == base + 'GAC4HostSeFmt/nested/1/GAC4HostSeSwitchCaseFmt/nested/1/InlinePayloadFmt.md'
    assert deep['parent_definition_id'] == nested[0]['definition_id']
    assert deep['nested_format_index'] == 1
    outer_text = (vault / parent['note']).read_text(encoding='utf-8')
    assert outer_text.count('<fmtDef id="GAC4HostSeSwitchCaseFmt"') == 2
    assert 'refid="AltMessageHeaderFmt"' in outer_text
    assert source.read_bytes() == original
    assert not (vault / 'vault-generation.json').exists()


@pytest.mark.parametrize('wrapper', [
    'AmtaIColl', 'CCIColl', 'ICollFEditQry', 'ICollFEditQryWEB',
    'IndexedCollectionFormatHolder', 'IndexedCollectionToFormat', 'IndexedCollFormat',
    'IColl', 'ICollSetLength', 'IndexCollectionFormatDLS', 'IndexCollectionFormatDLSWEB',
    'CCIndexedCollectionFormat',
])
def test_confirmed_indexed_wrappers_preserve_repeated_children(tmp_path, scoped_mapper, wrapper):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    channel = root / 'Channel/XML'
    channel.mkdir(parents=True)
    (channel / 'dse.ini').write_text('<dse.ini/>')
    source = channel / 'formats.xml'
    source.write_text(f'''<XML>
      <fmtDef id="Parent"><{wrapper}>
        <CCString dataName="Value" marker="FirstField"/>
        <CCString dataName="Value" marker="LastField"/>
        <fmtDef id="Repeated"><CCString dataName="FirstChild"/></fmtDef>
        <fmtDef id="Repeated"><CCString dataName="LastChild"/></fmtDef>
      </{wrapper}></fmtDef>
    </XML>''', encoding='utf-8')
    original = source.read_bytes()
    result = invoke_mapper(scoped_mapper, root, vault)
    assert result.returncode == 0, result.stderr
    formats = [entry for entry in read_vault_manifest(vault)['entities'] if entry['kind'] == 'format']
    assert len(formats) == 3
    parent = next(entry for entry in formats if entry['entity_id'] == 'Parent')
    text = (vault / parent['note']).read_text(encoding='utf-8')
    assert text.index('FirstField') < text.index('LastField')
    assert text.index('FirstChild') < text.index('LastChild')
    repeated = [entry for entry in formats if entry['entity_id'] == 'Repeated']
    assert len({entry['note'] for entry in repeated}) == 2
    assert len({entry['definition_id'] for entry in repeated}) == 2
    assert source.read_bytes() == original


@pytest.mark.parametrize('wrapper', ['CCXML', 'PS10NewXMLFormat', 'PS10XMLFormat', 'PSIONewXMLFormat', 'CustomWrapper'])
def test_keyed_wrappers_keep_last_child_and_its_decorators(tmp_path, scoped_mapper, wrapper):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    channel = root / 'Channel/XML'
    channel.mkdir(parents=True)
    (channel / 'dse.ini').write_text('''<dse.ini><kColl id="settings"><kColl id="tags"><kColl id="formats">
      <field id="TestDecorator" value="example.TestDecorator"/>
    </kColl></kColl></kColl></dse.ini>''')
    source = channel / 'formats.xml'
    source.write_text(f'''<XML>
      <CCDSEServerOperation id="A"><refFormat name="csRequestFormat" refid="Parent"/></CCDSEServerOperation>
      <fmtDef id="Parent"><{wrapper}>
        <CCString dataName="Value" marker="OldField"/>
        <TestDecorator marker="OldDecorator"/>
        <CCConstant dataName="Value" marker="NewField"/>
        <TestDecorator marker="NewDecorator"/>
        <CCString dataName="value" marker="DifferentCaseKey"/>
        <refFmt refid="Target"/><refFmt refid="Target"/>
        <CCString marker="UnnamedFirst"/><CCString marker="UnnamedSecond"/>
        <fmtDef id="Repeated"><CCString dataName="OldChild"/></fmtDef>
        <fmtDef id="Repeated"><CCString dataName="NewChild"/></fmtDef>
      </{wrapper}></fmtDef>
      <fmtDef id="OtherParent"><CCXML><fmtDef id="Repeated"><CCString dataName="OtherScope"/></fmtDef></CCXML></fmtDef>
    </XML>''', encoding='utf-8')
    original = source.read_bytes()
    result = invoke_mapper(scoped_mapper, root, vault)
    assert result.returncode == 0, result.stderr
    formats = [entry for entry in read_vault_manifest(vault)['entities'] if entry['kind'] == 'format']
    assert len(formats) == 4
    parent = next(entry for entry in formats if entry['entity_id'] == 'Parent')
    text = (vault / parent['note']).read_text(encoding='utf-8')
    for absent in ('OldField', 'OldDecorator', 'OldChild'):
        assert absent not in text
    for present in ('NewField', 'NewDecorator', 'NewChild', 'DifferentCaseKey', 'UnnamedFirst', 'UnnamedSecond'):
        assert present in text
    assert text.count('<refFmt refid="Target"') == 2
    repeated = [entry for entry in formats if entry['entity_id'] == 'Repeated']
    assert len(repeated) == 2
    assert any(entry['source_selector'] == f'/XML[1]/fmtDef[1]/{wrapper}[1]/fmtDef[2]' for entry in repeated)
    assert any(entry['source_selector'].startswith('/XML[1]/fmtDef[2]/') for entry in repeated)
    assert source.read_bytes() == original


def test_xml_error_includes_full_source_path_and_position(tmp_path, scoped_mapper):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    make_workspace(root)
    source = root / 'Channel/INTERNET/broken.xml'
    source.write_text('<XML>\n<value>A && B</value>\n</XML>')
    result = invoke_mapper(scoped_mapper, root, vault)
    assert result.returncode != 0
    assert '[XML parse error] ' + str(source.resolve()) + ':2:' in result.stderr
    assert 'entity reference' in result.stderr


@pytest.mark.parametrize('markdown', [True, False])
def test_bank_demo_repeated_calls_and_only_for_variants(tmp_path, scoped_mapper, markdown):
    root = Path(__file__).resolve().parents[2] / 'bank-demo/composer/Workspace'
    result = invoke_mapper(scoped_mapper, root, tmp_path, markdown)
    assert result.returncode == 0, result.stderr
    manifest = read_vault_manifest(tmp_path)
    graph = discover_operation_calls(tmp_path)
    assert graph['issues'] == []
    assert len(graph['operations']) == 10
    assert len(graph['calls']) == 7
    waves = operation_waves(graph)
    for channel, second_target in [('INTERNET', 'GetClientLinksOp'), ('IVR', 'GetAccountBalanceOp')]:
        caller = channel + '/ClientCallFlowDemoOp'
        calls = [call for call in graph['calls'] if call['caller'] == caller]
        assert [call['step'] for call in calls] == ['CallClientOperation', 'CallClientOperation']
        assert [call['callee'] for call in calls] == [channel + '/GetClientAccountsOp', channel + '/' + second_target]
        assert len({call['note'] for call in calls}) == 2
        steps = sorted([entry for entry in manifest['entities'] if entry['kind'] == 'opStep'
                        and entry['channel'] == channel and entry['operation_id'] == 'ClientCallFlowDemoOp'],
                       key=lambda entry: entry['step_index'])
        assert len(steps) == 2
        assert steps[0]['transition_targets'] == {'on0Do': steps[1]['note']}
        assert steps[1]['transition_targets'] == {}
        assert (tmp_path / steps[0]['note']).is_file() and (tmp_path / steps[1]['note']).is_file()
        assert waves[caller]['calls_count'] == 2 and waves[caller]['wave'] == 2
        assert not any(issue.get('operation') == caller for issue in manifest['diagnostics'])
    # Each source XML contains three occurrences; four are used and two stay in inventory.
    definitions = [entry for entry in manifest['entities'] if entry['kind'] == 'opStep'
                   and entry['entity_id'] == 'CallClientOperation']
    assert len(definitions) == 6
    assert len({entry['definition_id'] for entry in definitions}) == 6
    assert len([entry for entry in definitions if not entry['operation_id']]) == 2


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


@pytest.mark.parametrize('markdown', [True, False])
def test_excel_exporters_match_on_current_mapper_output(tmp_path, scoped_mapper, markdown):
    import shutil
    import sys
    project = Path(__file__).resolve().parents[2]
    python = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    python = str(python) if python.is_file() else sys.executable
    if subprocess.run([python, '-c', 'import openpyxl'], capture_output=True).returncode:
        pytest.skip('Workbook parity requires openpyxl')
    modules = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
    node = shutil.which('node')
    if not node or not (modules / '@oai/artifact-tool').exists():
        pytest.skip('Built-in workbook parity requires Node.js and @oai/artifact-tool')
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    shutil.copytree(project / 'bank-demo/composer/Workspace', root)
    source = root / 'WSBCC_XML/src/Xml Definition/Channel/XML/selfDefOper/CollectionRegression.xml'
    source.write_text('''<XML>
      <fmtDef id="Duplicate"><CCXML dataName="OldDefinition"/></fmtDef>
      <fmtDef id="Duplicate"><CCXML dataName="LastDefinition"/></fmtDef>
      <fmtDef id="IndexedParent"><CCIColl>
        <fmtDef id="Repeated"><CCString dataName="FirstChild"/></fmtDef>
        <fmtDef id="Repeated"><CCString dataName="SecondChild"/></fmtDef>
      </CCIColl></fmtDef>
      <fmtDef id="KeyedParent"><CCXML>
        <CCString dataName="Same" value="OldField"/>
        <CCString dataName="Same" value="LastField"/>
      </CCXML></fmtDef>
    </XML>''', encoding='utf-8')
    result = invoke_mapper(scoped_mapper, root, vault, markdown)
    assert result.returncode == 0, result.stderr
    manifest = read_vault_manifest(vault)
    formats = [entry for entry in manifest['entities'] if entry['kind'] == 'format'
               and entry['source_relative_path'].endswith('CollectionRegression.xml')]
    assert len(formats) == 5
    duplicate = next(entry for entry in formats if entry['entity_id'] == 'Duplicate')
    assert duplicate['source_selector'] == '/XML[1]/fmtDef[2]'
    assert len([entry for entry in formats if entry['entity_id'] == 'Repeated']) == 2
    keyed = next(entry for entry in formats if entry['entity_id'] == 'KeyedParent')
    assert 'OldField' not in (vault / keyed['note']).read_text(encoding='utf-8')
    isolated = tmp_path / 'portable'
    isolated.mkdir()
    script = isolated / 'Excel Generator.py'
    shutil.copy2(project / 'Excel Generator.py', script)
    standalone, builtin = tmp_path / 'standalone.xlsx', tmp_path / 'builtin.xlsx'
    environment = dict(os.environ, PYTHONPATH='')
    portable = subprocess.run([python, str(script), str(vault), '--output', str(standalone), '--include-relationships'],
                              cwd=isolated, env=environment, capture_output=True, text=True, timeout=120)
    assert portable.returncode == 0, portable.stderr
    built = subprocess.run([python, str(project / 'source/export_operation_migration.py'),
                            '--vault', str(vault), '--output', str(builtin), '--include-relationships',
                            '--node', node, '--artifact-modules', str(modules)],
                           cwd=isolated, env=environment, capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stderr
    for output in (portable.stdout, built.stdout):
        assert 'Validating Mapper vault' in output and 'Writing Excel workbook' in output
        assert '10 operations, 7 call sites, 0 issues' in output and 'Elapsed=' in output
    comparison = subprocess.run([python, '-c',
        "from openpyxl import load_workbook; import sys; a=load_workbook(sys.argv[1]); b=load_workbook(sys.argv[2]); "
        "assert a.sheetnames==b.sheetnames==['Migration Plan','Operations','Relationships']; "
        "assert all(list(a[s].values)==list(b[s].values) for s in a.sheetnames); a.close(); b.close()",
        str(standalone), str(builtin)], capture_output=True, text=True, timeout=30)
    assert comparison.returncode == 0, comparison.stderr


def test_standalone_discovery_matches_current_shared_implementation():
    import ast
    root = Path(__file__).resolve().parents[2]
    standalone = ast.parse((root / 'Excel Generator.py').read_text(encoding='utf-8-sig'))
    bundled = {node.name: ast.dump(node, include_attributes=False)
               for node in standalone.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    for relative in ('composer_mapper_tools/vault_manifest.py', 'composer_mapper_tools/manifest_json_stream.py',
                     'operation_call_tools/export_progress.py', 'operation_call_tools/discovery.py', 'operation_call_tools/ordering.py'):
        shared = ast.parse((root / 'source/tools' / relative).read_text(encoding='utf-8-sig'))
        for node in shared.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name != 'ordered_operations':
                assert bundled[node.name] == ast.dump(node, include_attributes=False), node.name


def test_parse_failure_never_publishes_complete_manifest(tmp_path, scoped_mapper):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    make_workspace(root)
    (root / 'Channel/INTERNET/broken.xml').write_text('<XML><broken>')
    result = invoke_mapper(scoped_mapper, root, vault)
    assert result.returncode != 0
    assert (vault / 'vault-generation.json').exists()
    assert not (vault / 'vault-manifest.json').exists()
    log = (vault / 'composer-mapper.log').read_text(encoding='utf-8')
    assert 'FAILED | elapsed=' in log and 'SUCCESS' not in log
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
