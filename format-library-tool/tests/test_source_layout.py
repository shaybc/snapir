"""Copied Java sources remain human-readable without weakening evidence verification."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from format_library.source_layout import copied_source_paths
from format_library.files import file_hash, read_json
from format_library.workspaces import prepare, verify_inputs
from format_library.planning import build_plan
from format_library.prompts import build_request
from test_tool import config, evidence, generate
from format_library.approval import approve


def test_package_paths_are_used_by_prompt_verification_and_approval(config):
    discovery = evidence(config, {'example.CCString': []})
    folder = prepare(config, build_plan(discovery))[0]
    manifest = read_json(folder / 'component.json')
    item = manifest['files'][0]
    assert item['path'] == 'sources/example/CCString.java'
    assert item['sha256'] == file_hash(item['original']) == file_hash(folder / item['path'])
    assert str(Path(item['original'])) in manifest['file_classes']
    assert item['path'] in (folder / 'prompt.txt').read_text()
    verify_inputs(folder, manifest)
    request = build_request(config, folder, manifest)
    assert item['path'] in request['attachments']
    generate(config, folder)
    published = approve(config, folder, reviewed=True)
    assert read_json(published / 'approval.json')['original_revisions']['example.CCString'] == item['sha256']
    assert prepare(config, build_plan(discovery))[0] == folder


def test_project_prefix_is_only_added_to_colliding_package_paths(tmp_path):
    first = str(tmp_path / 'Orders/src/Shared.java')
    second = str(tmp_path / 'Accounts/src/Shared.java')
    unique = str(tmp_path / 'Orders/src/Unique.java')
    classes = {
        'com.bank.First': dict(file=first, project=str(tmp_path / 'Orders')),
        'com.bank.Second': dict(file=second, project=str(tmp_path / 'Accounts')),
        'com.bank.Unique': dict(file=unique, project=str(tmp_path / 'Orders')),
    }
    names = {first: ['com.bank.First'], second: ['com.bank.Second'], unique: ['com.bank.Unique']}
    paths = copied_source_paths([first, second, unique], names, classes)
    assert paths[first] == 'sources/project-Orders/com/bank/Shared.java'
    assert paths[second] == 'sources/project-Accounts/com/bank/Shared.java'
    assert paths[unique] == 'sources/com/bank/Unique.java'


def test_same_project_names_get_readable_parent_names(tmp_path):
    first = str(tmp_path / 'North/Shared/src/Value.java')
    second = str(tmp_path / 'South/Shared/src/Value.java')
    names = {first: ['com.bank.First'], second: ['com.bank.Second']}
    classes = {name: dict(project=str(Path(path).parent.parent)) for path, values in names.items() for name in values}
    paths = copied_source_paths([first, second], names, classes)
    assert paths[first] == 'sources/project-North--Shared/com/bank/Value.java'
    assert paths[second] == 'sources/project-South--Shared/com/bank/Value.java'


@pytest.mark.parametrize('names,expected', [
    (['com.bank.Outer.Inner', 'com.bank.Outer'], 'sources/com/bank/Unit.java'),
    (['com.bank.First', 'com.bank.Second'], 'sources/com/bank/Unit.java'),
    (['Plain'], 'sources/Unit.java'),
])
def test_nested_types_multiple_types_and_default_package(tmp_path, names, expected):
    original = str(tmp_path / 'Unit.java')
    classes = {name: dict(project='Project') for name in names}
    assert copied_source_paths([original], {original: names}, classes)[original] == expected


def test_same_project_duplicate_path_is_rejected_before_copying(tmp_path):
    first, second = (str(tmp_path / root / 'Shared.java') for root in ('src-one', 'src-two'))
    names = {first: ['com.bank.First'], second: ['com.bank.Second']}
    classes = {name: dict(project='Project') for values in names.values() for name in values}
    with pytest.raises(ValueError, match='same project collide'):
        copied_source_paths([first, second], names, classes)
