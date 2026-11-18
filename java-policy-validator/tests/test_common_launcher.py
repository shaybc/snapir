"""The supported standalone launcher always compiles for the common Java target."""
import json
import os
from pathlib import Path
import subprocess
import sys
import yaml
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_launcher_reads_common_jdk_and_target_without_compile_flag(tmp_path):
    source = tmp_path / 'code'; source.mkdir()
    (source / 'Work.java').write_text('class Work {}')
    common = tmp_path / 'converter.yaml'
    common.write_text(yaml.safe_dump(dict(java_version=25,java_home=os.environ.get('JAVA_HOME'),
        model_name='unused-by-validator',framework_jars=['missing-ibm.jar'])))
    command = [sys.executable,str(ROOT / 'run.py'),'--code',str(source),'--common-config',str(common)]
    env = dict(os.environ, PYTHONPATH='')
    run = subprocess.run(command,capture_output=True,text=True,env=env,timeout=120)
    report = json.loads(run.stdout)
    assert run.returncode == 0, report
    assert report['compilation']['release'] == 25 and report['compilation']['status'] == 'passed'
    override = subprocess.run([*command,'--release','17'],capture_output=True,text=True,env=env,timeout=30)
    assert override.returncode == 0 and json.loads(override.stdout)['compilation']['release'] == 17


def test_validator_local_overrides_and_caller_overrides_reach_compilation(tmp_path):
    source = tmp_path / 'code'; source.mkdir()
    (source / 'Work.java').write_text('class Work {}')
    common = tmp_path / 'default_config.yaml'
    common.write_text(yaml.safe_dump(dict(java_version=21,java_home='./unavailable-jdk')))
    local = tmp_path / 'validator.yaml'
    local.write_text(yaml.safe_dump(dict(java_home=os.environ.get('JAVA_HOME'),java_version=25,target_java_version=17)))
    command = [sys.executable,str(ROOT / 'run.py'),'--code',str(source),'--common-config',str(common),'--config',str(local)]
    env = dict(os.environ, PYTHONPATH='')
    run = subprocess.run(command,capture_output=True,text=True,env=env,timeout=120)
    assert run.returncode == 0, run.stdout
    assert json.loads(run.stdout)['compilation']['release'] == 17
    run = subprocess.run([*command,'--release','25'],capture_output=True,text=True,env=env,timeout=120)
    assert run.returncode == 0 and json.loads(run.stdout)['compilation']['release'] == 25


@pytest.mark.parametrize('malformed', [False,True])
def test_invalid_common_file_is_a_structured_error(tmp_path, malformed):
    common = tmp_path / 'missing.yaml'
    if malformed:
        common.write_text('java_version: [broken')
    result = subprocess.run([sys.executable,str(ROOT / 'run.py'),'--code',str(tmp_path),
        '--common-config',str(common)],capture_output=True,text=True,timeout=30)
    assert result.returncode == 2
    expected = 'Invalid YAML' if malformed else 'Common converter configuration not found'
    assert expected in json.loads(result.stdout)['error']
