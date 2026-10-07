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
