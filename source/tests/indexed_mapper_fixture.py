"""Shared real-JDK/fat-JAR harness for indexed mapper acceptance checks."""

from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture(scope='session')
def indexed_mapper_jar():
    jar=ROOT/'source/composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar'
    assert jar.is_file(), 'Build first: mvn -f source/pom.xml package'
    return jar


def generate(jar,root,vault,*extra,heap='256m',check=True,timeout=900):
    log=vault.with_suffix('.log')
    with log.open('w',encoding='utf-8') as output:
        result=subprocess.run(['java','-Xmx'+heap,'-jar',str(jar),'--root',str(root),'--vault',str(vault),
            '--vault-layout','scoped','--workspace-id','bank','--md','true','--analysis-format','indexed-v1',*map(str,extra)],
            stdout=output,stderr=subprocess.STDOUT,text=True,timeout=timeout)
    if check:
        assert result.returncode==0,log.read_text(encoding='utf-8')[-6000:]
    return result,log


def workspace(root):
    sources=root/'src/pkg';sources.mkdir(parents=True)
    for name,body in dict(Step='Helper.value() + Helper.value()',Helper='Leaf.value()',Leaf='1',Unrelated='2').items():
        (sources/(name+'.java')).write_text(f'package pkg; public class {name} {{ public static int value() {{ return {body}; }} }}')
    for channel in ('XML','A','B','C'):
        folder=root/'src/Channel'/channel;folder.mkdir(parents=True)
        (folder/'dse.ini').write_text('<dse.ini/>')
        if channel!='XML':
            (folder/'ops.xml').write_text('<XML><CCDSEServerOperation id="Op"><opStep id="S" implClass="pkg.Step"/></CCDSEServerOperation></XML>')
    return root
