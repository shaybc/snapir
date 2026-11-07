"""Build relocated consumers with generated dependencies available only inside the package."""
import hashlib
from pathlib import Path
import subprocess
from types import SimpleNamespace

from models.pipeline_configuration import PipelineConfiguration
from models.maven_dependency import MavenDependency
from tools.shared_artifact_store.storage import ArtifactStore
from tools.shared_artifact_store.jars import compiled_jar, owned_class_entries
from tools.shared_artifact_store.project_repository import attach_repository
from tools.state_store_tools.component_reuse import record_component_use
from tools.state_store_tools.db import get_connection
from runtime.component_conversion.shared_dependencies import materialize_operation_dependencies
from runtime.java_toolchain import java_environment
from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier


def test_relocated_operation_resolves_its_bundled_shared_jar(tmp_path):
    environment = java_environment(25, None)
    source = tmp_path / 'library-source/shared/BaseValue.java'
    source.parent.mkdir(parents=True)
    source.write_text('package shared; public class BaseValue { public static String value(){return Helper.value();} } class Helper { static String value(){return "shared";} }')
    classes = tmp_path / 'library-classes'
    result = subprocess.run([str(Path(environment['JAVA_HOME']) / 'bin/javac.exe'), '-d', str(classes), str(source)],
                            capture_output=True, text=True, env=environment, timeout=60)
    assert result.returncode == 0, result.stderr
    entries = owned_class_entries(classes, [SimpleNamespace(path='src/main/java/shared/BaseValue.java', content=source.read_text())])
    assert entries == ['shared/BaseValue.class', 'shared/Helper.class']
    jar = compiled_jar(classes, entries)
    version = '1.0.0-' + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:16]
    coordinates = dict(group_id='il.co.dcd.converted', artifact_id='portable-base', version=version)
    dependency = MavenDependency(**coordinates, reason='Portable generated dependency')
    original_cache = Path.home() / '.m2/repository/il/co/dcd/converted/portable-base' / version
    assert not original_cache.exists()
    library_pom = ('<project><modelVersion>4.0.0</modelVersion><groupId>il.co.dcd.converted</groupId>'
                   '<artifactId>portable-base</artifactId><version>' + version + '</version></project>').encode()
    profile = PipelineConfiguration(shared_store_root=str(tmp_path / 'shared'), source_root=str(tmp_path))
    with ArtifactStore(profile.shared_store_root, 'components') as store:
        _, manifest = store.publish('portable-base-key', {'artifacts/base.jar': jar, 'artifacts/base.pom': library_pom,
            'source/BaseValue.java': source}, dict(validated=True, coordinates=coordinates, jar='artifacts/base.jar',
            pom='artifacts/base.pom', classes=entries, owned_sources=['src/main/java/shared/BaseValue.java']))
    config = SimpleNamespace(run_id='portable-consumer', output_root=str(tmp_path / 'run'))
    conn = get_connection(':memory:')
    record_component_use(conn, config.run_id, config.output_root, 'portable-base-key', manifest, group_id='base-group')
    operation = tmp_path / 'operation'
    main = operation / 'src/main/java/Caller.java'
    main.parent.mkdir(parents=True)
    main.write_text('public class Caller { public static void main(String[] args){System.out.print(shared.BaseValue.value());} }')
    pom = operation / 'pom.xml'
    pom.write_text('''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<groupId>example</groupId><artifactId>caller</artifactId><version>1</version>
<properties><maven.compiler.release>25</maven.compiler.release></properties>
<build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-compiler-plugin</artifactId><version>3.14.1</version></plugin></plugins></build>
<dependencies><dependency><groupId>il.co.dcd.converted</groupId><artifactId>portable-base</artifactId><version>''' + version + '</version></dependency></dependencies></project>')
    attach_repository(pom, [dependency])
    materialize_operation_dependencies(conn, config, profile, operation)
    conn.close()
    relocated = tmp_path / 'relocated operation'
    operation.rename(relocated)
    (tmp_path / 'shared').rename(tmp_path / 'unavailable-original-store')
    classes.rename(tmp_path / 'unavailable-original-classes')
    verifier = MavenRepositoryVerifier(None, [], None)
    verifier.environment = environment
    result = verifier.compile_project(relocated)
    assert result.returncode == 0, result.stdout + result.stderr
    jars = list((relocated / 'shared-dependencies/repository').rglob('*.jar'))
    import os
    result = subprocess.run([str(Path(environment['JAVA_HOME']) / 'bin/java.exe'), '-cp',
                             str(relocated / 'target/classes') + os.pathsep + str(jars[0]), 'Caller'],
                            capture_output=True, text=True, env=environment, timeout=60)
    assert result.returncode == 0 and result.stdout == 'shared', result.stderr
