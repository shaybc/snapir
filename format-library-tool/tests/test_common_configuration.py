"""Shared YAML selection, path ownership and prepared/worker handoffs use one configuration."""
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
import yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from format_library.configuration import load_config, source_configuration_hash
from format_library.common_configuration import load_common
from format_library.planning import build_plan
from format_library.prompts import build_request
from format_library.workspaces import prepare
from format_library.files import read_json
from test_tool import config, evidence, generate


@pytest.mark.parametrize('tool', ['format-library-tool/format_library', 'java-behavior-comparator/comparator', 'java-policy-validator'])
def test_independent_readers_resolve_common_paths_and_selection(tmp_path, monkeypatch, tool):
    monkeypatch.delenv('SNAPIR_COMMON_CONFIG', raising=False)
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('isolated_common_reader', root / tool / 'common_configuration.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    profile = tmp_path / 'configs/organization.yaml'; profile.parent.mkdir()
    profile.write_text(yaml.safe_dump(dict(source_root='../legacy', java_home='../jdk', java_version=25,
        classpath_jars=['../lib/a.jar'], framework_jars=['../lib/ibm.jar'],
        maven_settings_path='../maven/settings.xml', maven_local_repository='../maven/repository',
        eclipse_classpath_variables=dict(SERVER='../server'),
        eclipse_classpath_containers={'vendor/container':['../container/a.jar']},
        eclipse_project_classpath_containers={'project':{'vendor/container':['../project/b.jar']}},
        model_provider='litellm', model_name='openai/company-model', model_timeout_seconds=123,
        unrelated_converter_field={'ignored':True})))
    resolved = module.load_common(tmp_path / 'tool')
    for key, value in dict(source_root='legacy',java_home='jdk',maven_settings_path='maven/settings.xml',
                           maven_local_repository='maven/repository').items():
        assert resolved[key] == str((tmp_path / value).resolve())
    assert resolved['classpath_jars'] == [str(tmp_path / 'lib/a.jar')]
    assert resolved['eclipse_classpath_variables']['SERVER'] == str(tmp_path / 'server')
    assert resolved['eclipse_project_classpath_containers']['project']['vendor/container'] == [str(tmp_path / 'project/b.jar')]
    assert resolved['model_name'] == 'openai/company-model' and resolved['model_timeout_seconds'] == 123
    assert 'unrelated_converter_field' not in resolved
    second = profile.with_name('second.yaml'); second.write_text('{}')
    with pytest.raises(ValueError, match='Select the converter YAML'):
        module.load_common(tmp_path / 'tool')
    default = tmp_path / 'configs/default_config.yaml'; default.parent.mkdir(exist_ok=True)
    default.write_text('model_name: default-model\n')
    assert module.load_common(tmp_path / 'tool')['model_name'] == 'default-model'
    monkeypatch.setenv('SNAPIR_COMMON_CONFIG', str(profile))
    assert module.load_common(tmp_path / 'tool', configured=str(second))['_common_config_path'] == str(profile)
    assert module.load_common(tmp_path / 'tool', str(second))['_common_config_path'] == str(second)
    with pytest.raises(ValueError, match='not found'):
        module.load_common(tmp_path / 'tool', str(tmp_path / 'missing.yaml'))


def test_local_entries_override_common_without_changing_path_ownership(tmp_path, monkeypatch):
    monkeypatch.delenv('SNAPIR_COMMON_CONFIG', raising=False)
    (tmp_path / 'profiles').mkdir(); (tmp_path / 'tool').mkdir()
    common = tmp_path / 'profiles/organization.yaml'
    common.write_text(yaml.safe_dump(dict(source_root='../original', java_version=25, model_provider='litellm',
        model_name='openai/shared', model_base_url='https://company/v1', model_timeout_seconds=444,
        framework_jars=['../framework.jar'],eclipse_classpath_variables={'SERVER':'../server'})))
    local = tmp_path / 'tool/config.yaml'
    local.write_text(yaml.safe_dump(dict(common_config_path='../profiles/organization.yaml',source_root='./local-original',
        java_home=None,java_version=21,target_java_version=17,model_name='openai/local',output_root='./work',
        classpath_jars=['./lib/local.jar'],eclipse_classpath_variables={},
        eclipse_classpath_containers={'local/container':['./container/local.jar']},
        eclipse_project_classpath_containers={'project':{'container':['./container/project.jar']}})))
    result = load_config(local)
    assert result['source_root'] == str(tmp_path / 'tool/local-original')
    assert result['output_root'] == str(tmp_path / 'tool/work')
    assert result['java_version'] == 21 and result['target_java_version'] == 17
    assert result['model_name'] == 'openai/local' and result['model_timeout_seconds'] == 444
    assert result['model_base_url'] == 'https://company/v1' and result['java_home'] is None
    assert result['classpath_jars'] == [str(tmp_path / 'tool/lib/local.jar')]
    assert result['framework_jars'] == [str(tmp_path / 'framework.jar')]
    assert result['eclipse_classpath_variables'] == {}
    assert result['eclipse_classpath_containers']['local/container'] == [str(tmp_path / 'tool/container/local.jar')]
    assert result['eclipse_project_classpath_containers']['project']['container'] == [str(tmp_path / 'tool/container/project.jar')]


def test_tool_local_defaults_do_not_mask_common_values(tmp_path, monkeypatch):
    monkeypatch.delenv('SNAPIR_COMMON_CONFIG', raising=False)
    common = tmp_path / 'default_config.yaml'
    common.write_text('java_version: 21\nmodel_name: shared\nclasspath_jars: [shared.jar]\n')
    local = tmp_path / 'tool.yaml'; local.write_text('common_config_path: default_config.yaml\n')
    settings = load_config(local)
    assert settings['model_name'] == 'shared' and settings['target_java_version'] == 21
    assert settings['classpath_jars'] == [str(tmp_path / 'shared.jar')]
    local.write_text('common_config_path: default_config.yaml\nclasspath_jars: []\nmodel_name: ""\n')
    settings = load_config(local)
    assert settings['classpath_jars'] == [] and settings['model_name'] == ''


def test_repository_default_is_selected_without_inheriting_converter_output_settings(monkeypatch):
    from format_library.configuration import TOOL_ROOT
    monkeypatch.delenv('SNAPIR_COMMON_CONFIG', raising=False)
    settings = load_config(TOOL_ROOT / 'config.yaml')
    assert settings['_common_config_path'] == str(TOOL_ROOT.parent / 'configs/default_config.yaml')
    assert settings['output_root'] == str(TOOL_ROOT / 'work')


def test_local_null_java_and_maven_paths_are_preserved_through_validation(config):
    common = Path(config['_common_config_path'])
    values = yaml.safe_load(common.read_text())
    values.update(java_home='./missing-jdk',maven_settings_path='./missing-settings.xml',maven_local_repository='./missing-repo')
    common.write_text(yaml.safe_dump(values))
    local = Path(config['_config_path'])
    values = yaml.safe_load(local.read_text())
    values.update(java_home=None,maven_settings_path=None,maven_local_repository=None)
    local.write_text(yaml.safe_dump(values))
    effective = load_config(local)
    folder = prepare(effective, build_plan(evidence(effective, {'example.Work':[]})))[0]
    candidate = generate(effective, folder)
    assert read_json(candidate / 'candidate.json')['validation']['compilation']['status'] == 'passed'


def test_prepared_launcher_preserves_and_refreshes_common_profile_on_reuse(config):
    plan = build_plan(evidence(config, {'example.Work':[]}))
    folder = prepare(config, plan)[0]
    assert '--common-config "' + config['_common_config_path'] + '"' in (folder / 'convert.cmd').read_text()
    new_common = Path(config['_common_config_path']).with_name('another-common.yaml')
    new_common.write_text('{}')
    config['_common_config_path'] = str(new_common)
    prepare(config, plan)
    assert '--common-config "' + str(new_common) + '"' in (folder / 'convert.cmd').read_text()


def test_source_change_requires_rediscovery_but_model_change_reuses_evidence(config):
    data = evidence(config, {'example.Work':[]})
    data['source_configuration_hash'] = source_configuration_hash(config)
    plan = build_plan(data); folder = prepare(config, plan)[0]
    config['model_name'] = 'openai/new-model'
    assert prepare(config, plan) == [folder]
    config['classpath_jars'] = ['a-new.jar']
    with pytest.raises(ValueError, match='Discover and plan'):
        prepare(config, plan)
    with pytest.raises(ValueError, match='Source configuration changed'):
        build_request(config, folder, read_json(folder / 'component.json'))


def test_prepared_java_target_cannot_silently_override_common_java_version(config):
    folder = prepare(config, build_plan(evidence(config, {'example.Work':[]})))[0]
    config['target_java_version'] = 21
    with pytest.raises(ValueError, match='target Java version changed'):
        build_request(config, folder, read_json(folder / 'component.json'))


def test_model_worker_uses_the_parent_common_profile(config, tmp_path, monkeypatch):
    from format_library.model_client import receive
    seen = {}
    def process(command, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(stdout=io.StringIO('{"delta":"native result"}\n{"done":true}\n'),
            poll=lambda:0,wait=lambda:0)
    monkeypatch.setattr('format_library.model_client.subprocess.Popen', process)
    assert receive(config, tmp_path / 'request.json') == 'native result'
    assert seen['env']['SNAPIR_COMMON_CONFIG'] == config['_common_config_path']
