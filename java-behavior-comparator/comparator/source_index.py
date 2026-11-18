"""Build and invoke only this tool's AST indexer; keep inputs and outputs independently versioned."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import re
from comparator.configuration import ROOT
from comparator.models import digest, file_hash, save

JAR = ROOT / 'indexer/target/behavior-source-indexer-1.0.0-jar-with-dependencies.jar'


def environment(settings):
    """Select the configured JDK without importing another tool's environment helpers."""
    env = os.environ.copy()
    if settings['java_home']:
        env['JAVA_HOME']=settings['java_home']
        env['PATH']=str(Path(settings['java_home'])/'bin')+os.pathsep+env.get('PATH','')
    return env


def index(inputs, settings, work):
    """Persist an exact AST inventory, rebuilding only the independent indexer if necessary."""
    env=environment(settings)
    java=shutil.which('java',path=env.get('PATH'))
    if not java: raise ValueError('Java 17+ is required for source indexing')
    if settings.get('java_version'):
        version=subprocess.run([java,'-version'],env=env,capture_output=True,text=True,timeout=10)
        major=re.search(r'version\s+"(\d+)',version.stdout+version.stderr)
        if version.returncode or not major or int(major[1])!=settings['java_version']:
            raise ValueError('Selected JDK does not match common java_version='+str(settings['java_version']))
    paths=[ROOT/'indexer/pom.xml',*sorted((ROOT/'indexer/src').rglob('*.java'))]
    revision=digest({str(p.relative_to(ROOT)):file_hash(p) for p in paths})
    state=ROOT/'indexer/target/build-state.json'
    previous=json.loads(state.read_text()) if state.is_file() else {}
    if not JAR.is_file() or previous!=dict(inputs=revision,jar=file_hash(JAR)):
        command=shutil.which(settings['maven_command'],path=env.get('PATH'))
        if not command: raise ValueError('Maven is required to build the comparator indexer')
        build_command=[command,'-B','-f',str(ROOT/'indexer/pom.xml')]
        if settings.get('maven_settings_path'): build_command+=['-s',settings['maven_settings_path']]
        if settings.get('maven_local_repository'): build_command+=['-Dmaven.repo.local='+settings['maven_local_repository']]
        build=subprocess.run([*build_command,'package'],
                             env=env,stdout=sys.stderr,stderr=sys.stderr,timeout=settings['index_timeout_seconds'])
        if build.returncode: raise ValueError('Comparator indexer build failed')
        save(state,dict(inputs=revision,jar=file_hash(JAR)))
    fingerprint=digest(dict(inputs=inputs,indexer=revision,java=java,java_version=settings.get('java_version')))
    output=work/('index-'+fingerprint+'.json')
    receipt=output.with_suffix('.sha256.json')
    cached=json.loads(receipt.read_text()) if receipt.is_file() else {}
    if not output.is_file() or cached.get('sha256')!=file_hash(output):
        request=work/'index-input.json';save(request,inputs)
        result=subprocess.run([java,'-jar',str(JAR),str(request),str(output)],env=env,
                              capture_output=True,text=True,encoding='utf-8',timeout=settings['index_timeout_seconds'])
        (work/'indexer.stderr.txt').write_text(result.stderr,encoding='utf-8')
        if result.returncode: raise ValueError('AST indexing failed; see indexer.stderr.txt')
        save(receipt,dict(sha256=file_hash(output)))
    return json.loads(output.read_text(encoding='utf-8'))
