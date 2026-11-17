"""Independent CLI tests require only pytest and an already built validator JAR."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
JAR = ROOT / 'target/java-policy-validator-1.0.0-jar-with-dependencies.jar'


def run(tmp_path, files, policy=None):
    code = tmp_path / 'code'; code.mkdir()
    for name, content in files.items():
        path = code / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    rules = tmp_path / 'policy.json'
    rules.write_text(json.dumps(policy or json.loads((ROOT / 'policy.json').read_text())))
    result = subprocess.run([shutil.which('java'), '-jar', str(JAR), str(code), str(rules)],
                            capture_output=True, text=True, encoding='utf-8')
    report = json.loads(result.stdout)
    assert report['policy_hash'] == hashlib.sha256(rules.read_bytes()).hexdigest()
    return result, report


@pytest.mark.parametrize('source', [
    '/** {@code com.ibm.dse.Context} */ class Work { String text = "com.ibm.Legacy"; }',
    'class Work { String text = """\ncom.ibm.Legacy\n"""; }',
    'class Work { void invoke(){} void call(){invoke();} }',
])
def test_comments_and_data_are_not_dependencies(tmp_path, source):
    result, report = run(tmp_path, {'Work.java':source})
    assert result.returncode == 0, report
    assert report['status'] == 'passed' and not report['findings']
    assert report['files']['Work.java']


@pytest.mark.parametrize('source,rule', [
    ('import com.ibm.dse.Context; class Work {}','forbidden_java_dependency'),
    ('class Work extends com.ibm.dse.Base {}','forbidden_java_dependency'),
    ('@com.ibm.Flag class Work {}','forbidden_java_dependency'),
    ('class Work { void run(){com.ibm.Legacy.run();} }','forbidden_java_dependency'),
    ('class Work { Object run() throws Exception {return Class.forName("com.ibm.Legacy");} }','reflection'),
    ('class Work { Object run(Class<?> type) throws Exception {return type.getMethod("x");} }','reflection'),
    ('import java.lang.invoke.MethodHandles; class Work {}','reflection'),
    ('class Work { this is not valid }','java_syntax'),
])
def test_ast_rejections_have_actionable_findings(tmp_path, source, rule):
    result, report = run(tmp_path, {'Work.java':source})
    assert result.returncode == 1, report
    findings = [item for item in report['findings'] if item['rule'] == rule]
    assert findings and findings[0]['file'] == 'Work.java'
    assert findings[0]['line'] >= 1
    assert findings[0]['suggested_fix']


@pytest.mark.parametrize('declaration', [
    '<dependencies><dependency><groupId>com.ibm</groupId><artifactId>composer</artifactId><version>1.0</version></dependency></dependencies>',
    '<dependencies><dependency><groupId>example</groupId><artifactId>native</artifactId><version>${unknown}</version></dependency></dependencies>',
    '<repositories><repository><url>https://unknown.invalid</url></repository></repositories>',
    '<build><plugins><plugin><artifactId>exec-maven-plugin</artifactId><version>1.0</version></plugin></plugins></build>',
    '<parent><groupId>example</groupId><artifactId>parent</artifactId><version>1.0</version></parent>',
])
def test_maven_policy_rejects_unapproved_declarations(tmp_path, declaration):
    result, report = run(tmp_path, {'pom.xml':'<project>'+declaration+'</project>'})
    assert result.returncode == 1 and report['findings'], report


def test_exact_native_maven_allowlist_and_local_properties(tmp_path):
    policy = json.loads((ROOT / 'policy.json').read_text())
    policy['allowed_dependencies'] = ['example:native:1.2.3']
    result, report = run(tmp_path, {'pom.xml': '<project><properties><v>1.2.3</v></properties><dependencies><dependency><groupId>example</groupId><artifactId>native</artifactId><version>${v}</version></dependency></dependencies></project>'}, policy)
    assert result.returncode == 0, report


@pytest.mark.parametrize('name,text', [
    ('src/main/resources/META-INF/services/example.Provider', 'com.ibm.Provider\n'),
    ('src/main/resources/META-INF/services/com.ibm.Provider', 'example.Native\n'),
    ('src/main/resources/beans.xml', '<beans><bean class="com.ibm.Provider"/></beans>'),
])
def test_runtime_registrations(tmp_path, name, text):
    result, report = run(tmp_path, {name:text})
    assert result.returncode == 1, report
    assert any(item['rule']=='runtime_registration' for item in report['findings'])


def test_validator_errors_are_json(tmp_path):
    result = subprocess.run([shutil.which('java'), '-jar', str(JAR), str(tmp_path/'absent'), str(ROOT/'policy.json')], capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)['status'] == 'error'
