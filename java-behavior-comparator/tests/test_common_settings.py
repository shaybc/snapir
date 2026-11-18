"""Shared model settings drive standalone comparison without copying a second connection config."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import yaml
from comparator.configuration import load
from comparator.model_client import request


def test_local_connection_and_java_values_override_common_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv('SNAPIR_COMMON_CONFIG', raising=False)
    common = tmp_path / 'organization.yaml'
    common.write_text(yaml.safe_dump(dict(model_provider='gemini',model_name='shared-model',model_base_url='',
        model_api_key_environment='SHARED_KEY',java_version=25,java_home='./jdk',maven_settings_path='./settings.xml')))
    (tmp_path / 'tool').mkdir()
    local = tmp_path / 'tool/tool.yaml'
    local.write_text(yaml.safe_dump(dict(common_config_path='../'+common.name,model_name='local-model',
        java_home='./local-jdk',java_version=21,maven_local_repository='./maven',max_model_calls=12)))
    config = load(local)
    assert config['model_name'] == 'local-model' and config['model_provider'] == 'gemini'
    assert config['java_home'] == str(tmp_path / 'tool/local-jdk') and config['java_version'] == 21
    assert config['maven_settings_path'] == str(tmp_path / 'settings.xml') and config['max_model_calls'] == 12
    assert config['maven_local_repository'] == str(tmp_path / 'tool/maven')


@pytest.mark.parametrize('provider', ['gemini','litellm'])
def test_common_provider_uses_its_own_sdk_adapter(monkeypatch, provider):
    import sys
    from comparator.provider_transport import request_provider
    captured = {}
    class Client:
        def __init__(self, **kwargs):
            captured.update(kwargs); self.models = self
        def generate_content(self, **kwargs):
            captured.update(kwargs); return SimpleNamespace(text='{"ok":true}')
        def close(self): captured['closed'] = True
    def completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))])
    monkeypatch.setitem(sys.modules,'google.genai',SimpleNamespace(Client=Client))
    import google
    monkeypatch.setattr(google,'genai',sys.modules['google.genai'],raising=False)
    monkeypatch.setitem(sys.modules,'litellm',SimpleNamespace(completion=completion))
    monkeypatch.setenv('SHARED_TEST_KEY','not-a-real-key')
    config = dict(model_provider=provider,model_name='gemini/shared-model' if provider == 'gemini' else 'shared-model',
        model_base_url='',model_api_key_environment='SHARED_TEST_KEY')
    assert json.loads(request_provider(config,[dict(content='system'),dict(content='task')],42)) == {'ok':True}
    assert captured['api_key'] == 'not-a-real-key'
    if provider == 'gemini':
        assert captured['http_options'] == {'timeout':42000} and captured['closed']
        assert captured['model'] == 'shared-model'
    else:
        assert captured['model'] == 'shared-model' and captured['timeout'] == 42 and captured['stream'] is False
