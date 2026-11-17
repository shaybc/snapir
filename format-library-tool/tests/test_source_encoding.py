"""Original Java encoding is consistent across discovery and model attachments."""
import os
import sys
from pathlib import Path
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from format_library.configuration import load_config
from format_library.discovery import scan
from format_library.planning import build_plan
from format_library.workspaces import prepare, verify_inputs
from format_library.files import read_json, file_hash
from format_library.prompts import build_request


@pytest.mark.parametrize('encoding', ['UTF-8', 'windows-1255'])
def test_encoding_and_unreadable_file_do_not_stop_discovery(tmp_path, encoding):
    root = tmp_path / 'workspace'
    base = root / 'src/main/java/com/ibm/dse/base/FormatElement.java'
    base.parent.mkdir(parents=True)
    base.write_bytes('package com.ibm.dse.base; public abstract class FormatElement {}'.encode(encoding))
    parent = root / 'src/main/java/example/Parent.java'
    parent.parent.mkdir()
    text = 'package example; public abstract class Parent extends com.ibm.dse.base.FormatElement { public String format(){return "' + chr(0x5d0) + '";} }'
    parent.write_bytes(text.encode(encoding))
    target = parent.with_name('Format.java')
    target.write_bytes(b'package example; public class Format extends Parent {}')
    # Invalid in both encodings: malformed UTF-8 or an undefined windows-1255 byte.
    broken = parent.with_name('Broken.java')
    broken.write_bytes(b'package example; class Broken { // ' + bytes([0x81]) + b'\n}')
    config_path = tmp_path / 'config.yaml'
    config_path.write_text(yaml.safe_dump(dict(source_root=str(root), output_root=str(tmp_path / 'work'),
        source_encoding=encoding, java_home=os.environ.get('JAVA_HOME'), java_version=25)), encoding='utf-8')
    config = load_config(config_path)
    discovery = scan(config)
    assert 'example.Format' in discovery['classes']
    assert 'example.Broken' not in discovery['classes']
    log = Path(discovery['detailed_log']).read_text(encoding='utf-8')
    assert 'Unreadable Java source:' in log and str(broken) in log
    assert encoding.lower() in log.lower()
    assert discovery['source_warnings']
    plan = build_plan(discovery)
    group = next(item for item in plan['groups'] if item['members'] == ['example.Format'])
    assert not group['blockers'], group
    folder = prepare(config, plan, ['example.Format'])[-1]
    manifest = read_json(folder / 'component.json')
    assert manifest['source_encoding'] == encoding
    verify_inputs(folder, manifest)
    request = build_request(config, folder, manifest)
    assert any(text == content for content in request['attachments'].values())
    copied = next(item for item in manifest['files'] if item['original'] == str(parent))
    assert file_hash(folder / copied['path']) == file_hash(parent)


@pytest.mark.parametrize('encoding', ['', None, 123, 'not-a-real-encoding'])
def test_invalid_source_encoding_has_clear_configuration_error(tmp_path, encoding):
    config = tmp_path / 'config.yaml'
    config.write_text(yaml.safe_dump(dict(source_root=str(tmp_path), source_encoding=encoding)))
    with pytest.raises(ValueError, match='source_encoding'):
        load_config(config)
