"""Verify channel dependency discovery against freshly compiled mapper code."""

import shutil
import subprocess
from pathlib import Path

import pytest

from constants import JAVA_VERSION
from tools.composer_mapper_tools.channel_note_parser import parse_channel_note


@pytest.fixture(scope="module")
def mapper_classes(tmp_path_factory):
    if not shutil.which("javac") or not shutil.which("java"):
        pytest.skip("Mapper integration requires a JDK")
    root = Path(__file__).resolve().parents[1]
    classes = tmp_path_factory.mktemp("mapper-classes")
    sources = sorted((root / "composer-mapper/src/main/java").rglob("*.java"))
    result = subprocess.run(["javac", "--release", JAVA_VERSION, "-encoding", "UTF-8", "-d", str(classes),
                             *map(str, sources)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return classes


def workspace(tmp_path, imported="BASE"):
    root = tmp_path / "workspace"
    base = root / "Channel/XML"
    base.mkdir(parents=True)
    (base / 'dse.ini').write_text('''<dse.ini><kColl id="settings"><kColl id="tags"><kColl id="formats">
      <field id="XmlOnly" value="org.example.XmlShared"/></kColl></kColl></kColl></dse.ini>''')
    child = root / "Channel/INTERNET"
    parent = root / "Channel/BASE"
    child.mkdir(parents=True)
    parent.mkdir(parents=True)
    (child / "dse.ini").write_text(f'''<dse.ini><kColl id="import"><field id="{imported}"/></kColl>
      <kColl id="settings"><kColl id="files"><kColl id="selfDefOper">
      <operDef id="operation.xml" value="Op"/></kColl></kColl><kColl id="tags"><kColl id="formats">
      <field id="CCString" value="org.example.ChildString"/></kColl></kColl></kColl></dse.ini>''')
    (parent / "dse.ini").write_text('''<dse.ini><kColl id="settings"><kColl id="tags"><kColl id="formats">
      <field id="CCString" value="org.example.BaseString"/></kColl></kColl></kColl></dse.ini>''')
    (parent / "formats.xml").write_text('<XML><fmtDef id="SharedFmt"><CCString dataName="Field"/></fmtDef></XML>')
    (child / "operation.xml").write_text('''<XML><CCDSEServerOperation id="Op" operationContext="Ctx">
      <refFormat name="csRequestFormat" refid="SharedFmt"/></CCDSEServerOperation></XML>''')
    return root


def invoke(classes, root, vault):
    return subprocess.run(["java", "-cp", str(classes), "il.co.dcd.composermapper.Main",
                           "--root", str(root), "--vault", str(vault), "--md", "--channel", "INTERNET"],
                          capture_output=True, text=True, timeout=60)


def test_imported_formats_and_child_tag_override_survive_filter(tmp_path, mapper_classes):
    root = workspace(tmp_path)
    vault = tmp_path / "vault"
    result = invoke(mapper_classes, root, vault)
    assert result.returncode == 0, result.stderr
    assert (vault / "formats/SharedFmt.md").is_file()
    tags = parse_channel_note((vault / "channels/INTERNET.md").read_text(), "INTERNET")
    assert ("CCString", "org.example.ChildString", "INTERNET") in tags
    assert ("XmlOnly", "org.example.XmlShared", "INTERNET") in tags


def test_missing_import_is_not_silently_ignored(tmp_path, mapper_classes):
    root = workspace(tmp_path, imported="ABSENT")
    result = invoke(mapper_classes, root, tmp_path / "vault")
    assert result.returncode != 0
    assert "Missing imported channel definition" in result.stderr


def test_import_cycle_is_rejected(tmp_path, mapper_classes):
    root = workspace(tmp_path)
    (root / "Channel/BASE/dse.ini").write_text('<dse.ini><kColl id="import"><field id="INTERNET"/></kColl></dse.ini>')
    result = invoke(mapper_classes, root, tmp_path / "vault")
    assert result.returncode != 0
    assert "Channel import cycle" in result.stderr


def test_all_channel_notes_keep_unrelated_tag_mappings_separate(tmp_path, mapper_classes):
    root = workspace(tmp_path)
    ivr = root / "Channel/IVR"
    ivr.mkdir()
    (ivr / "dse.ini").write_text('''<dse.ini><kColl id="settings"><kColl id="files"><kColl id="selfDefOper">
      <operDef id="ivr.xml" value="IvrOp"/></kColl></kColl><kColl id="tags"><kColl id="formats">
      <field id="CCString" value="org.example.IvrString"/></kColl></kColl></kColl></dse.ini>''')
    vault = tmp_path / "vault"
    result = subprocess.run(["java", "-cp", str(mapper_classes), "il.co.dcd.composermapper.Main",
        "--root", str(root), "--vault", str(vault), "--md"], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert ("CCString", "org.example.ChildString", "INTERNET") in parse_channel_note(
        (vault / "channels/INTERNET.md").read_text(), "INTERNET")
    assert ("CCString", "org.example.IvrString", "IVR") in parse_channel_note(
        (vault / "channels/IVR.md").read_text(), "IVR")


def test_java_source_channel_association_precedes_import_filtering(tmp_path, mapper_classes):
    root = tmp_path / 'workspace'
    for project, channel, imported in [('arbitrary-a', 'INTERNET', 'BASE'), ('arbitrary-b', 'BASE', None),
                                       ('arbitrary-c', 'IVR', None), ('arbitrary-d', 'XML', None)]:
        source = root / project / 'src'
        declaration = source / 'Xml Definition/Channel' / channel
        declaration.mkdir(parents=True)
        imports = f'<kColl id="import"><field id="{imported}"/></kColl>' if imported else ''
        (declaration / 'dse.ini').write_text('<dse.ini>' + imports + '</dse.ini>')
        java = source / 'org/example' / (channel + 'Class.java')
        java.parent.mkdir(parents=True)
        java.write_text(f'package org.example;\npublic class {channel}Class {{}}')
    harness = tmp_path / 'DiscoveryChannels.java'
    harness.write_text('''import java.nio.file.Path;
import il.co.dcd.composermapper.service.FileDiscoveryService;
public class DiscoveryChannels {
  public static void main(String[] args) {
    new FileDiscoveryService().discover(Path.of(args[0]), args.length > 1 ? args[1] : null).stream()
      .filter(f -> f.path().toString().endsWith(".java"))
      .forEach(f -> System.out.println(f.path().getFileName() + "=" + f.channel()));
  }
}''')
    compile_result = subprocess.run(['javac', '--release', JAVA_VERSION, '-cp', str(mapper_classes),
        '-d', str(tmp_path), str(harness)], capture_output=True, text=True, timeout=30)
    assert compile_result.returncode == 0, compile_result.stderr
    import os
    command = ['java', '-cp', str(tmp_path) + os.pathsep + str(mapper_classes), 'DiscoveryChannels', str(root)]
    all_channels = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert all_channels.returncode == 0, all_channels.stderr
    assert set(all_channels.stdout.splitlines()) == {'INTERNETClass.java=INTERNET', 'BASEClass.java=BASE', 'IVRClass.java=IVR', 'XMLClass.java=XML'}
    selected = subprocess.run([*command, 'INTERNET'], capture_output=True, text=True, timeout=30)
    assert selected.returncode == 0, selected.stderr
    assert set(selected.stdout.splitlines()) == {'INTERNETClass.java=INTERNET', 'BASEClass.java=BASE', 'XMLClass.java=XML'}


@pytest.fixture(scope='module')
def chain_probe(tmp_path_factory, mapper_classes):
    source = tmp_path_factory.mktemp('channel-chain-probe') / 'ChannelChainProbe.java'
    source.write_text('''import java.nio.file.Path;
import il.co.dcd.composermapper.service.*;
public class ChannelChainProbe {
    public static void main(String[] args) {
        var files = new FileDiscoveryService().discover(Path.of(args[0]));
        System.out.println(new ChannelImportResolver().resolve(files, args[1]));
    }
}''')
    compiled = subprocess.run(['javac', '--release', JAVA_VERSION, '-cp', str(mapper_classes),
        '-d', str(mapper_classes), str(source)], capture_output=True, text=True, timeout=30)
    assert compiled.returncode == 0, compiled.stderr
    return mapper_classes


@pytest.mark.parametrize('channel', ['SME', 'IVR', 'CUSTOM'])
def test_every_channel_inherits_xml_without_explicit_import(tmp_path, chain_probe, channel):
    root = workspace(tmp_path)
    local = root / 'Channel' / channel
    local.mkdir()
    (local / 'dse.ini').write_text('<dse.ini/>')
    result = subprocess.run(['java', '-cp', str(chain_probe), 'ChannelChainProbe', str(root), channel],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f'[XML, {channel}]'


def test_xml_is_included_once_with_declared_imports(tmp_path, chain_probe):
    root = workspace(tmp_path, imported='XML')
    (root / 'Channel/INTERNET/dse.ini').write_text('''<dse.ini><kColl id="import">
      <field id="XML"/><field id="BASE"/><field id="XML"/></kColl></dse.ini>''')
    (root / 'Channel/BASE/dse.ini').write_text('<dse.ini><kColl id="import"><field id="XML"/></kColl></dse.ini>')
    result = subprocess.run(['java', '-cp', str(chain_probe), 'ChannelChainProbe', str(root), 'INTERNET'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '[XML, BASE, INTERNET]'
    base = subprocess.run(['java', '-cp', str(chain_probe), 'ChannelChainProbe', str(root), 'XML'],
                          capture_output=True, text=True, timeout=30)
    assert base.returncode == 0 and base.stdout.strip() == '[XML]'


def test_implicit_base_is_not_a_recursive_import_edge(tmp_path, chain_probe):
    root = workspace(tmp_path)
    (root / 'Channel/XML/dse.ini').write_text('<dse.ini><kColl id="import"><field id="INTERNET"/></kColl></dse.ini>')
    result = subprocess.run(['java', '-cp', str(chain_probe), 'ChannelChainProbe', str(root), 'INTERNET'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '[XML, BASE, INTERNET]'
    (root / 'Channel/INTERNET/dse.ini').write_text('<dse.ini><kColl id="import"><field id="XML"/></kColl></dse.ini>')
    cycle = subprocess.run(['java', '-cp', str(chain_probe), 'ChannelChainProbe', str(root), 'INTERNET'],
                           capture_output=True, text=True, timeout=30)
    assert cycle.returncode != 0 and 'Channel import cycle' in cycle.stderr


def test_missing_implicit_base_is_reported(tmp_path, mapper_classes):
    root = workspace(tmp_path)
    (root / 'Channel/XML/dse.ini').unlink()
    result = invoke(mapper_classes, root, tmp_path / 'vault')
    assert result.returncode != 0
    assert 'Missing implicit XML base channel definition for INTERNET' in result.stderr
    assert not (tmp_path / 'vault/vault-manifest.json').exists()
