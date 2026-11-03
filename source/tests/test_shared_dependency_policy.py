"""Prove shared version choices survive independent generation and coordinated repinning."""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET
import pytest
from models.maven_dependency import MavenDependency
from models.pipeline_configuration import PipelineConfiguration
from models.shared_dependency_policy import SharedDependencyPolicy
from runtime.dependency_policy import canonical_dependencies,dependency_policy_scope,check_resolved,inventory
from tools.maven_dependency_tools.shared_policy_pom import apply_shared_policy
from tools.state_store_tools import dependency_locks
from tools.conversion_tools.scoped_reuse.fingerprints import conversion_policy


def configured(tmp_path,version='2.18.2'):
    policy=SharedDependencyPolicy(description='Test-approved target versions',managed_versions={'com.fasterxml.jackson.core:jackson-databind':version},
        dependencies=[MavenDependency(group_id='com.fasterxml.jackson.core',artifact_id='jackson-databind',version=version,required_classes=['com.fasterxml.jackson.databind.ObjectMapper'])])
    path=tmp_path/(version+'.json');path.write_text(policy.model_dump_json())
    return PipelineConfiguration(dependency_policy_path=str(path))


def test_independent_requests_receive_same_pins_and_cannot_override_them(tmp_path):
    profile=configured(tmp_path);conn=sqlite3.connect(':memory:')
    with dependency_policy_scope(conn,'run',profile,first:={}):
        assert first['known_dependencies'][0]['version']=='2.18.2'
        pin=MavenDependency(group_id='example',artifact_id='codec',version='1',required_classes=['example.Codec'])
        check_resolved(profile,[pin],remember=True)
    with dependency_policy_scope(conn,'run',profile,second:={}):
        assert any(item['artifact_id']=='codec' and item['version']=='1' for item in second['known_dependencies'])
        with pytest.raises(ValueError,match='shared lock'):
            check_resolved(profile,[pin.model_copy(update={'version':'2'})])
    assert first['shared_dependency_policy']==second['shared_dependency_policy']


def test_only_explicit_historical_revalidation_can_repin_saved_build_inputs(tmp_path):
    profile=configured(tmp_path);saved=dict(group_id='com.fasterxml.jackson.core',artifact_id='jackson-databind',version='2.17.2',required_classes=['com.fasterxml.jackson.databind.ObjectMapper'])
    with pytest.raises(ValueError,match='requires'):canonical_dependencies(profile,[saved])
    aligned=canonical_dependencies(profile,[saved],historical=True)[0]
    assert aligned.version=='2.18.2' and aligned.required_classes==saved['required_classes']
    assert saved['version']=='2.17.2'


def test_lock_conflicts_are_atomic_and_policy_upgrade_retains_old_namespace(tmp_path):
    path=tmp_path/'locks.db';one=sqlite3.connect(path);two=sqlite3.connect(path)
    pin=MavenDependency(group_id='example',artifact_id='codec',version='1')
    dependency_locks.remember(one,'run','old',[pin]);one.commit()
    with pytest.raises(ValueError,match='lock conflict'):
        dependency_locks.remember(two,'run','old',[pin.model_copy(update={'version':'2'})])
    dependency_locks.remember(two,'run','new',[pin.model_copy(update={'version':'2'})]);two.commit()
    assert dependency_locks.read(one,'run','old')[0]['version']=='1'
    assert dependency_locks.read(one,'run','new')[0]['version']=='2'


def test_poms_share_versions_without_changing_dependency_scopes_and_are_idempotent(tmp_path):
    profile=configured(tmp_path);pom=tmp_path/'pom.xml'
    pom.write_text('<project><dependencies><dependency><groupId>com.fasterxml.jackson.core</groupId><artifactId>jackson-databind</artifactId><version>2.17.2</version><scope>test</scope></dependency></dependencies></project>')
    apply_shared_policy(pom,profile);first=pom.read_bytes();apply_shared_policy(pom,profile)
    root=ET.fromstring(first)
    assert root.findtext('dependencies/dependency/version')=='2.18.2'
    assert root.findtext('dependencies/dependency/scope')=='test'
    assert root.findtext('dependencyManagement/dependencies/dependency/version')=='2.18.2'
    assert pom.read_bytes()==first and len((tmp_path/'dependency_policy_audit.jsonl').read_text().splitlines())==1


def test_policy_identity_invalidates_old_reuse_and_preserves_per_artifact_bom_versions(tmp_path):
    one=configured(tmp_path);two=configured(tmp_path,'2.18.2.1')
    assert conversion_policy(one)!=conversion_policy(two)
    policy=SharedDependencyPolicy(description='BOM may carry distinct patch versions',managed_versions={'example:one':'1.0','example:two':'1.0.1'})
    assert policy.managed_versions['example:one']!=policy.managed_versions['example:two']


def test_unconfigured_runs_keep_existing_behavior_and_do_not_create_locks(tmp_path):
    profile=PipelineConfiguration();conn=sqlite3.connect(':memory:');payload={}
    with dependency_policy_scope(conn,'run',profile,payload):check_resolved(profile,[],remember=True)
    assert payload=={} and not conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    pom=tmp_path/'pom.xml';pom.write_text('<project/>');apply_shared_policy(pom,profile)
    assert pom.read_text()=='<project/>'


def test_policy_cannot_change_during_generation(tmp_path):
    profile=configured(tmp_path);conn=sqlite3.connect(':memory:')
    with dependency_policy_scope(conn,'run',profile,{}):
        path=Path(profile.dependency_policy_path);original=path.read_text()
        path.write_text(original.replace('2.18.2','2.18.3'))
        with pytest.raises(ValueError,match='changed during generation'):inventory(profile)


def test_resolved_transitive_conflict_is_rejected_before_compilation(tmp_path,monkeypatch):
    from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier
    profile=configured(tmp_path);verifier=MavenRepositoryVerifier(None,[],None);verifier.dependency_profile=profile;calls=[]
    def execute(arguments,directory):
        calls.append(arguments)
        target=next((arg.split('=',1)[1] for arg in arguments if arg.startswith('-DoutputFile=')),None)
        if target:Path(target).write_text(json.dumps({'children':[dict(groupId='com.fasterxml.jackson.core',artifactId='jackson-databind',version='2.17.2',scope='compile')]}))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(verifier,'_run',execute)
    with pytest.raises(ValueError,match='requires'):verifier.compile_project(tmp_path)
    assert len(calls)==1


def test_transitive_jars_disambiguate_imports_without_guessing_or_relaxing_pins(tmp_path):
    from zipfile import ZipFile
    from runtime.behavior_conversion.native_metadata import resolve_dependencies
    profile=configured(tmp_path);profile.maven_local_repository=str(tmp_path/'repository')
    conn=sqlite3.connect(':memory:');pins=[]
    for artifact,classes in [('junit-jupiter-api',['org/junit/jupiter/api/Test.class','org/junit/jupiter/api/Assertions.class']),
        ('junit-jupiter-engine',['org/junit/jupiter/engine/Engine.class']),('junit-jupiter',[])]:
        pin=MavenDependency(group_id='org.junit.jupiter',artifact_id=artifact,version='5.10.0',scope='test');pins.append(pin)
        path=Path(profile.maven_local_repository)/'org/junit/jupiter'/artifact/pin.version/(artifact+'-'+pin.version+'.jar');path.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(path,'w') as jar:
            for name in classes:jar.writestr(name,b'class-inventory-fixture')
    with dependency_policy_scope(conn,'run',profile,{}):check_resolved(profile,pins,remember=True)
    with dependency_policy_scope(conn,'run',profile,payload:={}):
        imports=[dict(name='org.junit.jupiter.api.Test',static='false',wildcard='false'),dict(name='org.junit.jupiter.api.Assertions.assertEquals',static='true',wildcard='false')]
        selected,missing=resolve_dependencies(dict(types={},imports=imports),payload['known_dependencies'])
        assert not missing and [(p.artifact_id,p.version) for p in selected]==[('junit-jupiter-api','5.10.0')]
        assert selected[0].required_classes==['org.junit.jupiter.api.Assertions','org.junit.jupiter.api.Test']
        duplicate=Path(profile.maven_local_repository)/'org/junit/jupiter/junit-jupiter/5.10.0/junit-jupiter-5.10.0.jar'
        with ZipFile(duplicate,'w') as jar:jar.writestr('org/junit/jupiter/api/Test.class',b'duplicate-owner')
        _,missing=resolve_dependencies(dict(types={},imports=imports[:1]),payload['known_dependencies'])
        assert missing==['org.junit.jupiter.api.Test']
