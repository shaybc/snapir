"""Choose target dependencies without making every supporting import a conversion obligation."""

import json
from pathlib import Path
from zipfile import ZipFile
import pytest

from models.pipeline_configuration import PipelineConfiguration
from models.java_classpath_index import JavaClasspathIndex
from models.external_dependency import ExternalDependencyRule
from models.native_unit_bundle import NativeSourceFile, NativeUnitBundle
from tools.conversion_tools.dependency_treatment import dependency_record, retained_record
from runtime.retained_libraries.catalog import library_scope, current
from runtime.retained_libraries.artifacts import materialize, restore_portable, verify_portable, verify_library
from tests.test_scoped_closure import import_workspace
from tests.test_scoped_vault_identity import scoped_mapper
from tests.test_scoped_workflow import settings, prepare


def archive(path, *names, coordinates=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, 'w') as jar:
        for name in names:
            jar.writestr(name.replace('.', '/') + '.class', b'fixture')
        if coordinates:
            group, artifact, version = coordinates
            jar.writestr('META-INF/maven/' + group + '/' + artifact + '/pom.properties',
                         'groupId=' + group + '\nartifactId=' + artifact + '\nversion=' + version)
    return 'jar:' + str(path)


def policy(root, **values):
    return PipelineConfiguration(source_root=str(root), **values)


def test_retained_library_compiles_and_runs_after_relocation_without_original_jar(tmp_path):
    """Exercise real javac/Maven and a fresh offline cache, rather than mocked receipts."""
    import os
    import subprocess
    from types import SimpleNamespace
    from runtime.java_toolchain import java_environment
    from runtime.retained_libraries.build import attach_build_context
    from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier
    from models.maven_dependency import MavenDependency
    environment = java_environment(25, None)
    source = tmp_path / 'vendor-source/vendor/Client.java'
    source.parent.mkdir(parents=True)
    source.write_text('package vendor; public class Client { public static String value(){return "retained";} }')
    classes = tmp_path / 'vendor-classes'
    result = subprocess.run([str(Path(environment['JAVA_HOME']) / 'bin/javac.exe'), '-d', str(classes), str(source)],
                            capture_output=True, text=True, env=environment, timeout=60)
    assert result.returncode == 0, result.stderr
    jar_path = tmp_path / 'vendor.jar'
    with ZipFile(jar_path, 'w') as jar:
        jar.write(classes / 'vendor/Client.class', 'vendor/Client.class')
    record = retained_record('vendor.Client', 'jar:' + str(jar_path), policy(tmp_path), 'test')
    unused = retained_record('com.dynatrace.oneagent.sdk.OneAgentSDKFactory',
        archive(tmp_path / 'unused-tracing.jar', 'com.dynatrace.oneagent.sdk.OneAgentSDKFactory'), policy(tmp_path), 'test')
    dependency = MavenDependency.model_validate(record['library']['dependency'])
    settings_path = tmp_path / 'offline-settings.xml'
    settings_path.write_text('<settings><mirrors><mirror><id>offline-test</id><mirrorOf>*</mirrorOf><url>' +
        (Path.home() / '.m2/repository').as_uri() + '</url></mirror></mirrors></settings>')
    project = tmp_path / 'original'
    main = project / 'src/main/java/Caller.java'
    main.parent.mkdir(parents=True)
    main.write_text('public class Caller { public static void main(String[] args){System.out.print(vendor.Client.value());} }')
    (project / 'pom.xml').write_text('''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<groupId>example</groupId><artifactId>caller</artifactId><version>1</version>
<properties><maven.compiler.release>25</maven.compiler.release></properties>
<build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-compiler-plugin</artifactId><version>3.14.1</version></plugin></plugins></build>
<dependencies><dependency><groupId>''' + dependency.group_id + '</groupId><artifactId>' + dependency.artifact_id +
        '</artifactId><version>' + dependency.version + '</version></dependency></dependencies></project>')

    def context(folder, cache):
        profile = policy(tmp_path, maven_settings_path=str(settings_path), maven_local_repository=str(cache))
        verifier = MavenRepositoryVerifier(str(settings_path), [], str(cache))
        verifier.environment = environment
        return attach_build_context(SimpleNamespace(verifier=verifier, allowed_ibm_artifacts=()), profile, folder)

    with library_scope(policy(tmp_path), {'external_dependencies': [record, unused]}):
        build = context(project, tmp_path / 'original-cache')
        build.verifier(dependency)
        result = build.verifier.compile_project(project)
        assert result.returncode == 0, result.stdout + result.stderr
    lock = verify_portable(project / 'retained-dependencies')
    assert set(lock['libraries']) == {dependency.coordinates}
    relocated = tmp_path / 'relocated project'
    project.rename(relocated)
    jar_path.unlink()
    build = context(relocated, tmp_path / 'fresh-cache')
    result = build.verifier.compile_project(relocated)
    assert result.returncode == 0, result.stdout + result.stderr
    jars = list((relocated / 'retained-dependencies/repository').rglob('*.jar'))
    result = subprocess.run([str(Path(environment['JAVA_HOME']) / 'bin/java.exe'), '-cp',
        str(relocated / 'target/classes') + os.pathsep + str(jars[0]), 'Caller'],
        capture_output=True, text=True, env=environment, timeout=60)
    assert result.returncode == 0 and result.stdout == 'retained', result.stderr
    jars[0].write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='changed'):
        build.verifier.compile_project(relocated)


@pytest.mark.parametrize('name', ['oracle.jdbc.OracleTypes', 'com.dynatrace.oneagent.sdk.OneAgentSDKFactory'])
def test_verified_third_party_is_retained_without_per_class_configuration(tmp_path, name):
    location = archive(tmp_path / 'library.jar', name)
    record = dependency_record(name, [], policy(tmp_path), 'test', JavaClasspathIndex(classes={name: [location]}), required=True)
    assert record['treatment'] == 'retain'
    assert record['library']['dependency']['group_id'] == 'snapir.retained'
    assert record['scope'] == 'source_evidence_candidate'


def test_shared_component_restores_retained_library_without_original_source(tmp_path):
    """A reused generated component carries its retained dependencies into its consumer."""
    from types import SimpleNamespace
    from tools.shared_artifact_store.storage import ArtifactStore
    from tools.shared_artifact_store.maven import install_artifact
    from tools.state_store_tools.component_reuse import record_component_use
    from tools.state_store_tools.db import get_connection
    from runtime.component_conversion.shared_dependencies import materialize_operation_dependencies
    original = tmp_path / 'vendor.jar'
    profile = policy(tmp_path, shared_store_root=str(tmp_path / 'shared'), maven_local_repository=str(tmp_path / 'cache'))
    record = retained_record('vendor.Client', archive(original, 'vendor.Client'), profile, 'test')
    component = tmp_path / 'component'
    component.mkdir()
    (component / 'pom.xml').write_text('<project/>')
    materialize(record['library'], profile, component, tmp_path / 'build-cache')
    retained = component / 'retained-dependencies'
    files = {'artifacts/component.jar': b'component fixture', 'artifacts/component.pom': b'<project/>'}
    files.update({'artifacts/retained-dependencies/' + path.relative_to(retained).as_posix(): path
                  for path in retained.rglob('*') if path.is_file()})
    coordinates = dict(group_id='il.co.dcd.converted', artifact_id='component', version='1')
    with ArtifactStore(profile.shared_store_root, 'components') as store:
        directory, manifest = store.publish('component-key', files, dict(validated=True, coordinates=coordinates,
            jar='artifacts/component.jar', pom='artifacts/component.pom', retained_dependencies='artifacts/retained-dependencies'))
        original.unlink()
        install_artifact(directory, manifest, profile)
    config = SimpleNamespace(run_id='retained-consumer', output_root=str(tmp_path / 'run'))
    conn = get_connection(':memory:')
    record_component_use(conn, config.run_id, config.output_root, 'component-key', manifest, group_id='component')
    consumer = tmp_path / 'consumer'
    consumer.mkdir()
    (consumer / 'pom.xml').write_text('<project><dependencies><dependency><groupId>il.co.dcd.converted</groupId>'
        '<artifactId>component</artifactId><version>1</version></dependency></dependencies></project>')
    materialize_operation_dependencies(conn, config, profile, consumer)
    conn.close()
    assert set(verify_portable(consumer / 'retained-dependencies')['libraries']) == {record['maven_coordinates']}
    assert list((tmp_path / 'cache/snapir/retained').rglob('*.jar'))


def test_real_archive_coordinates_are_used_and_overrides_cannot_change_them(tmp_path):
    location = archive(tmp_path / 'library.jar', 'vendor.Client', coordinates=('vendor', 'client', '1.2.3'))
    profile = policy(tmp_path)
    record = retained_record('vendor.Client', location, profile, 'test')
    assert record['maven_coordinates'] == 'vendor:client:1.2.3'
    with pytest.raises(ValueError, match='disagree'):
        retained_record('vendor.Client', location, profile, 'test', {'maven_coordinates': 'vendor:client:9'})


def test_original_snapshot_uses_content_pin_without_allowing_snapshot_target_dependencies(tmp_path):
    record = retained_record('vendor.Client', archive(tmp_path / 'snapshot.jar', 'vendor.Client',
        coordinates=('vendor', 'client', '1-SNAPSHOT')), policy(tmp_path), 'test')
    assert record['library']['original_coordinates'] == 'vendor:client:1-SNAPSHOT'
    assert record['library']['dependency']['group_id'] == 'snapir.retained'


def test_documented_parent_needs_no_source_unknown_composer_uses_source_or_reports_gap(tmp_path):
    profile = policy(tmp_path)
    documented = dependency_record('com.ibm.il.dse.cc.format.AbstractFormatElement', [], profile, 'test', JavaClasspathIndex(), required=True)
    assert documented['treatment'] == 'replace' and documented['behavior_evidence']
    unknown = 'com.ibm.il.dse.cc.custom.UnknownImplementation'
    assert dependency_record(unknown, [], profile, 'test', JavaClasspathIndex(), source_exists=True, required=True) is None
    with pytest.raises(ValueError, match='lacks documentation and project source'):
        dependency_record(unknown, [], profile, 'test', JavaClasspathIndex(), required=True)
    assert dependency_record(unknown, [], profile, 'test', JavaClasspathIndex())['treatment'] == 'candidate'


def test_explicit_third_party_replacement_and_application_source_are_preserved(tmp_path):
    profile = policy(tmp_path)
    rules = [ExternalDependencyRule(class_name='vendor.Client', treatment='replace', behavior_description='Use a native HTTP client')]
    assert dependency_record('vendor.Client', rules, profile, 'test', JavaClasspathIndex())['treatment'] == 'replace'
    assert dependency_record('app.Helper', [], profile, 'test', JavaClasspathIndex(), source_exists=True) is None


def test_other_ibm_clients_need_original_approval_and_composer_cannot_be_retained(tmp_path):
    location = archive(tmp_path / 'ibm.jar', 'com.ibm.mq.Client', coordinates=('com.ibm.mq', 'client', '1'))
    classpath = JavaClasspathIndex(classes={'com.ibm.mq.Client': [location]})
    with pytest.raises(ValueError, match='exception'):
        dependency_record('com.ibm.mq.Client', [], policy(tmp_path), 'test', classpath, required=True)
    for approval in ({'allowed_ibm_classes': ['com.ibm.mq.Client']}, {'allowed_ibm_artifacts': ['com.ibm.mq:client:1']}):
        profile = policy(tmp_path, **approval)
        record = dependency_record('com.ibm.mq.Client', [], profile, 'test', classpath, required=True)
        assert verify_library(record['library'], profile).ibm
    rule = ExternalDependencyRule(class_name='com.ibm.dse.base.Context', treatment='retain')
    with pytest.raises(ValueError, match='must be replaced'):
        dependency_record('com.ibm.dse.base.Context', [rule], policy(tmp_path), 'test', classpath, required=True)


def test_saved_ibm_library_rechecks_original_approval_without_generation_scope(tmp_path):
    from runtime.retained_libraries.build import portable_approvals
    profile = policy(tmp_path, allowed_ibm_classes=['com.ibm.mq.Client'])
    record = retained_record('com.ibm.mq.Client', archive(tmp_path / 'mq.jar', 'com.ibm.mq.Client',
        coordinates=('com.ibm.mq', 'client', '1')), profile, 'test')
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'pom.xml').write_text('<project/>')
    materialize(record['library'], profile, project, tmp_path / 'cache')
    assert portable_approvals(project, profile) == {'com.ibm.mq:client:1'}
    with pytest.raises(ValueError, match='approval'):
        portable_approvals(project, policy(tmp_path))


def test_absent_and_ambiguous_supporting_libraries_are_candidates_not_fake_verified_origins(tmp_path):
    for locations in ([], ['jar:a.jar', 'jar:b.jar']):
        record = dependency_record('vendor.Optional', [], policy(tmp_path), 'test', JavaClasspathIndex(classes={'vendor.Optional': locations}))
        assert record['treatment'] == 'candidate'
        assert 'library' not in record


def test_full_supporting_source_reaches_preparation_even_with_unused_missing_library(tmp_path, scoped_mapper):
    def change(root):
        (root / 'src/example/Work.java').write_text('''package example;
import com.dynatrace.oneagent.sdk.OneAgentSDKFactory;
public class Work { public int execute() { return 0; }
  public void unrelated() { OneAgentSDKFactory.createInstance(); } }
''')
    conn, root, vault = import_workspace(tmp_path, scoped_mapper, change=change)
    try:
        config, profile = settings(root, vault)
        result = prepare(conn, config, profile)
        assert all(item['status'] == 'prepared' for item in result['operations'].values()), {
            key: item['blockers'] for key, item in result['operations'].items()}
        operation = result['operations']['SME/Flow']
        assert any('public void unrelated()' in source['content'] for unit in operation['units'] for source in unit['sources'])
        assert any(item['class_name'].endswith('OneAgentSDKFactory') and item['treatment'] == 'candidate'
                   for item in operation['behavior_request']['external_dependencies'])
    finally:
        conn.close()


def test_only_selected_libraries_are_materialized_and_portable_hashes_survive_relocation(tmp_path):
    profile = policy(tmp_path)
    records = [retained_record(name, archive(tmp_path / (name + '.jar'), name), profile, 'test') for name in ('vendor.Client', 'trace.Unused')]
    payload = {'external_dependencies': records}
    project = tmp_path / 'original'
    project.mkdir()
    (project / 'pom.xml').write_text('<project><modelVersion>4.0.0</modelVersion></project>')
    with library_scope(profile, payload):
        assert len(current()[1]) == 2
        assert not (project / 'retained-dependencies').exists()
        materialize(records[0]['library'], profile, project, tmp_path / 'cache')
    lock = verify_portable(project / 'retained-dependencies')
    assert len(lock['libraries']) == 1
    assert records[1]['maven_coordinates'] not in lock['libraries']
    relocated = tmp_path / 'relocated'
    restore_portable(project / 'retained-dependencies', relocated, tmp_path / 'fresh-cache')
    assert verify_portable(relocated) == lock
    jar = next((relocated / 'repository').rglob('*.jar'))
    jar.write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        verify_portable(relocated)


def test_original_jar_and_pom_changes_are_rejected(tmp_path):
    profile = policy(tmp_path)
    path = tmp_path / 'library.jar'
    record = retained_record('vendor.Client', archive(path, 'vendor.Client'), profile, 'test')
    path.with_suffix('.pom').write_text('<project/>')
    with pytest.raises(ValueError, match='metadata changed'):
        verify_library(record['library'], profile)
    path.with_suffix('.pom').unlink()
    path.write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed or is missing'):
        verify_library(record['library'], profile)


def test_local_wrapper_cannot_hide_composer_runtime(tmp_path):
    profile = policy(tmp_path)
    record = retained_record('vendor.Client', archive(tmp_path / 'mixed.jar', 'vendor.Client', 'com.ibm.dse.base.Context'), profile, 'test')
    with pytest.raises(ValueError, match='prohibited Composer'):
        verify_library(record['library'], profile)


def test_multi_release_jar_cannot_hide_composer_runtime(tmp_path):
    profile = policy(tmp_path)
    path = tmp_path / 'multi-release.jar'
    archive(path, 'vendor.Client')
    with ZipFile(path, 'a') as jar:
        jar.writestr('META-INF/versions/17/com/ibm/dse/base/Context.class', b'fixture')
    record = retained_record('vendor.Client', 'jar:' + str(path), profile, 'test')
    with pytest.raises(ValueError, match='Composer runtime'):
        verify_library(record['library'], profile)


def test_java_packager_checks_retained_bytes(tmp_path):
    import os
    import subprocess
    from runtime.java_toolchain import java_environment
    profile = policy(tmp_path)
    record = retained_record('vendor.Client', archive(tmp_path / 'vendor.jar', 'vendor.Client'), profile, 'test')
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'pom.xml').write_text('<project/>')
    materialize(record['library'], profile, project, tmp_path / 'cache')
    templates = Path('source/templates/native_operations/standalone').resolve()
    repository = Path.home() / '.m2/repository/com/fasterxml/jackson/core'
    cp = os.pathsep.join(str(repository / name / '2.18.2' / (name + '-2.18.2.jar'))
                         for name in ('jackson-databind', 'jackson-core', 'jackson-annotations'))
    probe = tmp_path / 'RetainedProbe.java'
    probe.write_text('import java.nio.file.*; public class RetainedProbe { public static void main(String[] args) throws Exception { PackageRetainedDependencies.verify(Path.of(args[0])); } }')
    environment = java_environment(25, None)
    classes = tmp_path / 'classes'
    result = subprocess.run([str(Path(environment['JAVA_HOME']) / 'bin/javac.exe'), '-cp', cp, '-d', str(classes),
        str(probe), str(templates / 'DemoBinding.java'), str(templates / 'packaging/PackageFiles.java'),
        str(templates / 'packaging/PackageRetainedDependencies.java')], capture_output=True, text=True, env=environment, timeout=60)
    assert result.returncode == 0, result.stderr
    arguments = [str(Path(environment['JAVA_HOME']) / 'bin/java.exe'), '-cp', str(classes) + os.pathsep + cp,
                 'RetainedProbe', str(project)]
    assert subprocess.run(arguments, capture_output=True, env=environment, timeout=60).returncode == 0
    next((project / 'retained-dependencies').rglob('*.jar')).write_bytes(b'changed')
    result = subprocess.run(arguments, capture_output=True, text=True, env=environment, timeout=60)
    assert result.returncode != 0 and 'Retained dependency changed' in result.stderr


def test_approved_ibm_client_passes_source_guard_but_composer_and_other_clients_do_not(tmp_path):
    from runtime.behavior_conversion.bundle_output import validate_bundle
    from runtime.behavior_conversion.side_road_policy import ForbiddenFrameworkDependency
    profile = policy(tmp_path, allowed_ibm_classes=['com.ibm.mq.Client'])
    record = retained_record('com.ibm.mq.Client', archive(tmp_path / 'mq.jar', 'com.ibm.mq.Client'), profile, 'test')
    def bundle(owner):
        return NativeUnitBundle(files=[NativeSourceFile(path='src/main/java/com/company/generated/demo/Native.java',
            content='package com.company.generated.demo; public class Native { ' + owner + ' client; }')])
    with library_scope(profile, {'external_dependencies': [record]}):
        assert validate_bundle(bundle('com.ibm.mq.Client'))
        with pytest.raises(ForbiddenFrameworkDependency):
            validate_bundle(bundle('com.ibm.other.Unapproved'))
        with pytest.raises(ForbiddenFrameworkDependency):
            validate_bundle(bundle('com.ibm.dse.base.Context'), allowed_classes=['com.ibm.dse.base.Context'])


def test_scope_instruction_is_shared_by_direct_staged_and_correction_requests():
    from agents.behavior_conversion.operation_scope import INSTRUCTION
    from agents.behavior_conversion.native_instructions import COMMON_INSTRUCTION
    from agents.behavior_conversion.staged_instructions import IMPLEMENTATION_CONTRACT
    from runtime.behavior_conversion.compiler_feedback import CORRECTION_INSTRUCTION
    assert all(INSTRUCTION in value for value in (COMMON_INSTRUCTION, IMPLEMENTATION_CONTRACT, CORRECTION_INSTRUCTION))
