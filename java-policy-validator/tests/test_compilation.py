"""Every standalone validator invocation must compile without running candidate code."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from test_validator import ROOT, run


@pytest.mark.parametrize('source', [
    'class Work { int value(){return "wrong";} }',
    'class Work implements Runnable {}',
    'class Work { missing.NativeDependency field; }',
    'import com.fasterxml.jackson.databind.ObjectMapper; class Work { ObjectMapper value; }',
])
def test_syntax_valid_but_uncompilable_candidates_fail(tmp_path, source):
    process, report = run(tmp_path, {'Work.java':source})
    assert process.returncode == 1, report
    assert report['compilation']['status']=='failed'
    assert not any(finding['rule']=='java_syntax' for finding in report['findings'])
    findings=[finding for finding in report['findings'] if finding['rule']=='compilation']
    assert findings and findings[0]['file']=='Work.java'
    assert findings[0]['line'] > 0
    assert findings[0]['suggested_fix']
    assert report['compilation']['diagnostics'][0]['code']


def test_native_support_sources_and_release_are_compiled(tmp_path):
    support=tmp_path/'native';support.mkdir()
    api=support/'NativeApi.java';api.write_text('public interface NativeApi { int value(); }')
    process, report=run(tmp_path, {'Work.java':'class Work implements NativeApi { public int value(){return 1;} }'},
        context=dict(source_roots=[str(support)],release=17))
    assert process.returncode==0, report
    assert report['compilation']['status']=='passed'
    assert report['compilation']['support_files']=={'support/0/NativeApi.java':hashlib.sha256(api.read_bytes()).hexdigest()}
    assert report['compilation']['release']==17
    assert not list(tmp_path.rglob('*.class'))


def test_forbidden_support_code_cannot_bypass_policy(tmp_path):
    support=tmp_path/'native';support.mkdir()
    (support/'Legacy.java').write_text('package com.ibm; public class Legacy {}')
    process, report=run(tmp_path, {'Work.java':'class Work {}'},context=dict(source_roots=[str(support)]))
    assert process.returncode==1
    assert any(item['rule']=='forbidden_java_dependency' and item['file'].startswith('support/') for item in report['findings'])


def test_full_jdk_is_required_even_for_simple_valid_code(tmp_path):
    process, report=run(tmp_path, {'Work.java':'class Work {}'},java_options=['--limit-modules','java.se'])
    assert process.returncode==2, report
    assert report['status']=='error' and 'javac is unavailable' in report['error']


def test_approved_classpath_and_annotation_processors_are_disabled(tmp_path):
    library=tmp_path/'library';library.mkdir()
    source=library/'Api.java';source.write_text('package nativeapi; public interface Api { int value(); }')
    processor=library/'Tripwire.java';processor.write_text('''package processor;
        public class Tripwire extends javax.annotation.processing.AbstractProcessor {
            public java.util.Set<String> getSupportedAnnotationTypes(){return java.util.Set.of("*");}
            public boolean process(java.util.Set<? extends javax.lang.model.element.TypeElement> a,
                javax.annotation.processing.RoundEnvironment b){throw new IllegalStateException("Processor must not run");}
        }''')
    classes=library/'classes';classes.mkdir()
    subprocess.run([shutil.which('javac'),'--release','17','-proc:none','-d',str(classes),str(source),str(processor)],check=True,capture_output=True)
    services=classes/'META-INF/services';services.mkdir(parents=True)
    (services/'javax.annotation.processing.Processor').write_text('processor.Tripwire')
    archive=library/'native.jar'
    subprocess.run([shutil.which('jar'),'--create','--file',str(archive),'-C',str(classes),'.'],check=True,capture_output=True)
    policy=json.loads((ROOT/'policy.json').read_text())
    policy['allowed_dependencies']=['example:native:1.0']
    policy['compile_classpath']=[dict(coordinate='example:native:1.0',path=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest())]
    process,report=run(tmp_path,{'Work.java':'class Work implements nativeapi.Api { public int value(){return 1;} }'},policy)
    assert process.returncode==0, report
    assert report['compilation']['status']=='passed'
    assert report['compilation']['classpath_files']


def test_compilation_does_not_initialize_generated_classes(tmp_path):
    marker=tmp_path/'executed'
    source='class Work { static { try { java.nio.file.Files.writeString(java.nio.file.Path.of("'+marker.as_posix()+'"),"ran"); } catch(Exception e) {throw new RuntimeException(e);} } }'
    process,report=run(tmp_path,{'Work.java':source})
    assert process.returncode==0, report
    assert report['compilation']['status']=='passed'
    assert not marker.exists()


@pytest.mark.parametrize('context', [dict(source_roots='not-a-list'), dict(release='17'), dict(source_roots=[None])])
def test_invalid_compilation_inputs_are_errors(tmp_path, context):
    process, report = run(tmp_path, {'Work.java':'class Work {}'}, context=context)
    assert process.returncode == 2, report
    assert report['status'] == 'error'


def test_missing_or_changed_approved_jar_is_not_accepted(tmp_path):
    policy=json.loads((ROOT/'policy.json').read_text())
    policy['allowed_dependencies']=['example:native:1.0']
    policy['compile_classpath']=[dict(coordinate='example:native:1.0',path=str(tmp_path/'missing.jar'),sha256='0'*64)]
    process,report=run(tmp_path,{'Work.java':'class Work {}'},policy)
    assert process.returncode==2, report
    assert 'Compilation JAR is missing or its hash differs' in report['error']
