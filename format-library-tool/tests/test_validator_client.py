"""Generation accepts only a matching passing report from the external CLI."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from format_library.validator_client import validate
from format_library.files import read_json
from format_library.generated_files import extract
from format_library.planning import build_plan
from format_library.workspaces import prepare
from test_tool import config, evidence, response, generate


@pytest.mark.parametrize('explicit', [False,True])
def test_only_explicit_formatter_java_and_maven_overrides_are_forwarded(tmp_path, monkeypatch, explicit):
    from format_library.configuration import DEFAULTS
    settings = dict(DEFAULTS, validator_command=['external'],
        _local_shared_fields=['java_home','java_version','maven_settings_path','maven_local_repository'] if explicit else [])
    code = tmp_path/'code';code.mkdir()
    (code/'Work.java').write_text('class Work {}')
    attempt = tmp_path/'attempt';attempt.mkdir()
    received = []
    def run(command, **kwargs):
        received.extend(command)
        raise FileNotFoundError('Synthetic validator; only inspecting configuration arguments')
    monkeypatch.setattr('format_library.validator_client.subprocess.run',run)
    with pytest.raises(ValueError,match='External validation'):
        validate(settings,code,attempt)
    for flag in ('--java-home','--java-version','--maven-settings-path','--maven-local-repository'):
        assert (flag in received) is explicit
    assert '--release' in received
    if explicit:
        assert received[received.index('--java-home')+1] == ''


@pytest.mark.parametrize('release', [17,25])
def test_real_cli_accepts_documentation_and_preserves_last_candidate_on_failure(config, release):
    config['target_java_version'] = release
    folder = prepare(config, build_plan(evidence(config, {'example.Work': []})))[0]
    manifest = read_json(folder / 'component.json')
    payload = json.loads(response(manifest))
    native = next(iter(manifest['native_classes'].values())).rsplit('.', 1)[-1]
    payload['files'][0]['content'] = payload['files'][0]['content'].replace('public class ' + native + ' {}',
        'public class ' + native + ' implements com.snapir.format.api.NativeFormat {'
        'public com.snapir.format.api.XmlElement format(Object value, com.snapir.format.api.FormatContext context){return null;}'
        'public Object unformat(com.snapir.format.api.XmlElement value, com.snapir.format.api.FormatContext context){return null;} }')
    payload['files'][0]['content'] = '/** {@code com.ibm.dse.Legacy} */\n'+payload['files'][0]['content']
    attempt = folder / 'attempts/documentation'; attempt.mkdir()
    accepted = extract(folder, manifest, json.dumps(payload), dict(prerequisites=[]), attempt, config=config)
    before = (folder / 'latest.json').read_bytes()
    assert read_json(attempt/'validation.json')['status']=='passed'
    assert read_json(accepted/'candidate.json')['validation']['status']=='passed'
    assert read_json(attempt/'validation.json')['compilation']['status']=='passed'
    assert read_json(attempt/'validation.json')['compilation']['release']==release
    assert read_json(attempt/'validation.json')['compilation']['support_files']
    invalid = json.loads(json.dumps(payload))
    invalid['files'][0]['content'] += '\nclass Invalid { int number(){return "wrong";} }'
    compile_attempt = folder / 'attempts/uncompilable'; compile_attempt.mkdir()
    with pytest.raises(ValueError, match='validation'):
        extract(folder, manifest, json.dumps(invalid), dict(prerequisites=[]), compile_attempt, config=config)
    assert read_json(compile_attempt/'validation.json')['compilation']['status']=='failed'
    assert not (folder/'generated/uncompilable').exists()
    assert (folder/'latest.json').read_bytes()==before
    payload['files'][0]['content'] += '\nclass Helper { com.ibm.dse.Context context; }'
    attempt = folder / 'attempts/rejected'; attempt.mkdir()
    with pytest.raises(ValueError, match='validation'):
        extract(folder, manifest, json.dumps(payload), dict(prerequisites=[]), attempt, config=config)
    assert read_json(attempt/'validation.json')['status']=='failed'
    assert (attempt/'candidate').is_dir()
    assert not (folder/'generated/rejected').exists()
    assert (folder/'latest.json').read_bytes()==before


@pytest.mark.parametrize('mode', ['missing','malformed','exit','stale','timeout','error','no_compile','wrong_release','wrong_support'])
def test_client_fails_closed(tmp_path, monkeypatch, mode):
    staged = tmp_path/'candidate'; staged.mkdir()
    (staged/'Work.java').write_text('class Work {}')
    attempt=tmp_path/'attempt'; attempt.mkdir()
    policy=tmp_path/'policy.json';policy.write_text('{}')
    def run(*args, **kwargs):
        if mode=='missing': raise FileNotFoundError('missing validator')
        if mode=='timeout': raise subprocess.TimeoutExpired(args[0],1)
        if mode=='malformed': return SimpleNamespace(returncode=0,stdout='not JSON',stderr='')
        files={'Work.java':hashlib.sha256((staged/'Work.java').read_bytes()).hexdigest()}
        report=dict(schema_version='java-policy-validation-v1',status='passed',files=files,
            policy_hash=hashlib.sha256(policy.read_bytes()).hexdigest(), input_hash=hashlib.sha256(
                json.dumps(files,separators=(',',':')).encode()).hexdigest(),
            findings=[],tool_version='1',policy_version='1',checks=['compilation'],
            compilation=dict(status='passed',release=17,support_files={}))
        if mode=='no_compile': report.pop('compilation')
        if mode=='wrong_release': report['compilation']['release']=25
        if mode=='wrong_support': report['compilation']['support_files']={'stale':'hash'}
        if mode=='stale': report['files']={}
        if mode=='error': report['status']='error'
        return SimpleNamespace(returncode=2 if mode in {'exit','error'} else 0,stdout=json.dumps(report),stderr='')
    monkeypatch.setattr('format_library.validator_client.subprocess.run',run)
    with pytest.raises(ValueError,match='External validation'):
        validate(dict(validator_command=['external'],validator_policy_path=str(policy)),staged,attempt)
    assert (attempt/'validation-rejection.json').is_file()
